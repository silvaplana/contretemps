package cloud.silvaplana.fights.camera

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.BatteryManager
import android.os.Handler
import android.os.HandlerThread
import android.os.IBinder
import android.os.PowerManager
import android.util.Log
import java.io.File
import java.io.IOException
import java.util.concurrent.Executors

/**
 * Tourne en continu tant que le téléphone de la salle est jumelé : demande
 * toutes les 5 s au serveur s'il faut filmer (« Démarrer la séance » /
 * « Fin de séance » dans Fights), filme, et envoie les morceaux.
 */
class RecorderService : Service() {

    private lateinit var prefs: Prefs
    private lateinit var folder: File
    private lateinit var uploader: Uploader
    private val thread = HandlerThread("camera").apply { start() }
    private val handler = Handler(thread.looper)
    private val sender = Executors.newSingleThreadExecutor()
    private var wakeLock: PowerManager.WakeLock? = null
    private var recorder: PieceRecorder? = null
    private var recordingSession: Int? = null

    override fun onCreate() {
        super.onCreate()
        prefs = Prefs(this)
        folder = File(filesDir, "pieces").apply { mkdirs() }
        uploader = Uploader(folder)
        wakeLock = getSystemService(PowerManager::class.java)
            .newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "fights:camera").apply { acquire() }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        startForeground(
            NOTIFICATION, notification("Prête"),
            ServiceInfo.FOREGROUND_SERVICE_TYPE_CAMERA or ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE,
        )
        running = true
        handler.removeCallbacksAndMessages(null)
        handler.post(::tick)
        return START_STICKY
    }

    override fun onDestroy() {
        running = false
        handler.removeCallbacksAndMessages(null)
        handler.post {
            recorder?.stop(last = false)
            thread.quitSafely()
        }
        sender.shutdown()
        wakeLock?.release()
        status = Status()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    /** Toutes les 5 s, sur le fil de la caméra. */
    private fun tick() {
        val token = prefs.token
        if (token == null) {
            stopSelf()
            return
        }
        val api = Api(prefs.server, token)
        try {
            val orders = api.heartbeat(recorder != null, battery(), folder.usableSpace, uploader.pending().size)
            follow(orders)
            status = status.copy(online = true, error = null)
        } catch (e: Api.Error) {
            if (e.status == 403) {
                // Un autre téléphone a été jumelé à la place de celui-ci.
                prefs.token = null
                status = status.copy(online = false, error = "Téléphone remplacé : jumelez-le de nouveau.")
                recorder?.stop(last = true)
                recorder = null
                stopSelf()
                return
            }
            status = status.copy(online = false, error = "Serveur : erreur ${e.status}")
        } catch (e: IOException) {
            status = status.copy(online = false, error = "Pas de réseau")
        }
        status = status.copy(pending = uploader.pending().size)
        handler.postDelayed(::tick, TICK_MS)
    }

    private fun follow(orders: Api.Orders) {
        val wanted = orders.sessionId
        status = status.copy(wanted = wanted != null)
        if (wanted == recordingSession) return
        if (recordingSession != null) stopRecording()
        if (wanted != null && !previewing) startRecording(wanted)
    }

    private fun startRecording(sessionId: Int) {
        val key = "position_$sessionId"
        lateinit var pieces: PieceRecorder
        pieces = PieceRecorder(
            this, folder, sessionId, prefs.int(key), handler,
            onPosition = { prefs.setInt(key, it) },
            onPiece = ::send,
            onError = { message ->
                Log.w(TAG, message)
                status = status.copy(error = message)
                // La séance continue au prochain tour, dans un nouveau morceau.
                handler.post { if (recorder === pieces) stopRecording(last = false) }
            },
        )
        try {
            pieces.start()
        } catch (e: Exception) {
            Log.w(TAG, "start", e)
            status = status.copy(error = "Caméra indisponible")
            return
        }
        recorder = pieces
        recordingSession = sessionId
        status = status.copy(recording = true, since = System.currentTimeMillis())
        notify("Filme la séance")
    }

    private fun stopRecording(last: Boolean = true) {
        val pieces = recorder ?: return
        recorder = null
        recordingSession = null
        pieces.stop(last)
        status = status.copy(recording = false, since = null)
        notify("Prête")
    }

    private fun send() {
        sender.execute {
            val token = prefs.token ?: return@execute
            uploader.sendAll(Api(prefs.server, token))
            status = status.copy(pending = uploader.pending().size)
        }
    }

    private fun battery(): Int? =
        getSystemService(BatteryManager::class.java).getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)
            .takeIf { it in 0..100 }

    private fun notification(text: String): Notification {
        val manager = getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(NotificationChannel(CHANNEL, "Caméra", NotificationManager.IMPORTANCE_LOW))
        val open = PendingIntent.getActivity(
            this, 0, Intent(this, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE,
        )
        return Notification.Builder(this, CHANNEL)
            .setSmallIcon(R.drawable.ic_camera)
            .setContentTitle(getString(R.string.app_name))
            .setContentText(text)
            .setContentIntent(open)
            .setOngoing(true)
            .build()
    }

    private fun notify(text: String) =
        getSystemService(NotificationManager::class.java).notify(NOTIFICATION, notification(text))

    /** Ce que l'écran affiche (MainActivity le relit chaque seconde). */
    data class Status(
        val online: Boolean = false,
        val recording: Boolean = false,
        /** Fights demande de filmer (l'écran lâche alors la caméra). */
        val wanted: Boolean = false,
        val since: Long? = null,
        val pending: Int = 0,
        val error: String? = null,
    )

    companion object {
        private const val TAG = "RecorderService"
        private const val TICK_MS = 5_000L
        private const val CHANNEL = "camera"
        private const val NOTIFICATION = 1

        @Volatile var status = Status()
        @Volatile var running = false
        /** L'écran montre l'image de la caméra : on ne démarre pas tant qu'il la tient. */
        @Volatile var previewing = false

        fun start(context: Context) = context.startForegroundService(Intent(context, RecorderService::class.java))
    }
}
