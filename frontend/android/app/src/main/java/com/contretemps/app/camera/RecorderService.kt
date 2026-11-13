package com.contretemps.app.camera

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
import com.contretemps.app.MainActivity
import com.contretemps.app.R
import java.io.File
import java.io.IOException
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean

/**
 * Tourne en continu tant que l'appli Tournage est sur « Caméra » (Fights ›
 * Tournage) : demande toutes les 5 s au serveur s'il faut filmer (bouton
 * Filmer / Arrêter, ici ou sur une télécommande), filme, et envoie les
 * morceaux. Repris tel quel de l'appli caméra à part (recorder/).
 */
class RecorderService : Service() {

    private lateinit var prefs: Prefs
    private lateinit var folder: File
    private lateinit var uploader: Uploader
    private val thread = HandlerThread("camera").apply { start() }
    private val handler = Handler(thread.looper)
    private val sender = Executors.newSingleThreadExecutor()
    private val sending = AtomicBoolean(false)
    private var wakeLock: PowerManager.WakeLock? = null
    private val tickTask = Runnable { tick() }
    private var recorder: PieceRecorder? = null
    private var recordingSession: Int? = null

    override fun onCreate() {
        super.onCreate()
        prefs = Prefs(this)
        folder = File(filesDir, "pieces").apply { mkdirs() }
        uploader = Uploader(folder)
        upload = uploader
        wakeLock = getSystemService(PowerManager::class.java)
            .newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "fights:camera").apply { acquire() }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        startForeground(
            NOTIFICATION, notification("Prête"),
            ServiceInfo.FOREGROUND_SERVICE_TYPE_CAMERA or ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE,
        )
        running = true
        finishing = false
        handler.removeCallbacksAndMessages(null)
        handler.post(tickTask)
        // Filmer / Arrêter sur ce téléphone : il demande ses ordres tout de suite (Seb, 13/11).
        poke = {
            handler.removeCallbacks(tickTask)
            handler.post(tickTask)
        }
        return START_STICKY
    }

    override fun onDestroy() {
        running = false
        poke = {}
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
        handler.removeCallbacks(tickTask) // un tour en double (poke) n'en fait pas deux chaînes
        val token = prefs.token
        if (token == null) {
            stopSelf()
            return
        }
        val api = Api(prefs.server, token)
        // Plus sur « Caméra » : ne filme plus, finit d'envoyer, puis s'arrête (Seb, 12/11).
        if (finishing) {
            stopRecording()
            status = status.copy(pending = uploader.pending().size, wanted = false)
            if (status.pending == 0 && !sending.get()) {
                prefs.token = null
                stopSelf()
                return
            }
            send()
            handler.postDelayed(tickTask, TICK_MS)
            return
        }
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
        // Un envoi coupé (réseau, serveur) reprend ici, même une fois le film arrêté.
        if (status.pending > 0) send()
        handler.postDelayed(tickTask, TICK_MS)
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

    /** Un seul envoi à la fois ; ce qui arrive pendant est repris au tour suivant. */
    private fun send() {
        if (!sending.compareAndSet(false, true)) return
        sender.execute {
            try {
                val token = prefs.token ?: return@execute
                // Le compte des morceaux en attente est remis à jour par tick().
                uploader.sendAll(Api(prefs.server, token))
            } finally {
                sending.set(false)
            }
        }
    }

    private fun battery(): Int? =
        getSystemService(BatteryManager::class.java).getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)
            .takeIf { it in 0..100 }

    private fun notification(text: String): Notification {
        val manager = getSystemService(NotificationManager::class.java)
        // Pas de pastille « 1 » sur l'icône pour cette notification permanente (Seb, 12/11).
        // Un canal ne change plus une fois créé : nouveau nom, l'ancien est effacé.
        manager.deleteNotificationChannel("camera")
        manager.createNotificationChannel(
            NotificationChannel(CHANNEL, "Caméra", NotificationManager.IMPORTANCE_LOW).apply { setShowBadge(false) },
        )
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

    /** Ce que Fights › Tournage affiche (TournagePlugin.status). */
    data class Status(
        val online: Boolean = false,
        val recording: Boolean = false,
        /** Le serveur demande de filmer (l'image de Tournage lâche alors la caméra). */
        val wanted: Boolean = false,
        val since: Long? = null,
        val pending: Int = 0,
        val error: String? = null,
    )

    companion object {
        private const val TAG = "RecorderService"
        // Toutes les 2 s (Seb, 13/11 : Filmer depuis une télécommande doit répondre vite).
        private const val TICK_MS = 2_000L
        private const val CHANNEL = "tournage"
        private const val NOTIFICATION = 1

        @Volatile var status = Status()
        /** L'envoi en cours, lu par TournagePlugin.status. */
        @Volatile var upload: Uploader? = null
        @Volatile var running = false
        /** Tournage montre l'image de la caméra : on ne démarre pas tant qu'il la tient. */
        @Volatile var previewing = false
        /** Quitté « Caméra » pendant un envoi : il continue, puis le service s'arrête. */
        @Volatile var finishing = false
        /** Demande ses ordres au serveur sans attendre le prochain tour. */
        @Volatile var poke: () -> Unit = {}

        fun start(context: Context) = context.startForegroundService(Intent(context, RecorderService::class.java))
    }
}
