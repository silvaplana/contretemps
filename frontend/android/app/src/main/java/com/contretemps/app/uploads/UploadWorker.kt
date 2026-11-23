package com.contretemps.app.uploads

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.util.Log
import androidx.work.CoroutineWorker
import androidx.work.ForegroundInfo
import androidx.work.WorkerParameters
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import com.contretemps.app.MainActivity
import com.contretemps.app.R
import java.io.IOException
import java.io.RandomAccessFile

/**
 * Envoie les vidéos de la file (VideoQueue), par blocs, dans l'ordre. Tâche de
 * premier plan avec une notification : Android la laisse finir appli fermée.
 * Une coupure de réseau n'est pas grave : la vidéo reste sur le téléphone et
 * WorkManager relance la tâche (`Result.retry`), qui repart là où le serveur
 * s'est arrêté.
 */
class UploadWorker(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        var retry = false
        for (upload in VideoQueue.pending(applicationContext)) {
            if (isStopped) return Result.retry()
            setForeground(foregroundInfo())
            try {
                withContext(Dispatchers.IO) { send(upload) }
                VideoQueue.forget(applicationContext, upload.id)
            } catch (e: Api.Refused) {
                // Le serveur ne veut plus de cet envoi (annulé, nettoyé…) :
                // personne ne l'attend, la vidéo quitte le téléphone.
                Log.w(TAG, "${upload.id} : ${e.status} ${e.message}")
                VideoQueue.forget(applicationContext, upload.id)
            } catch (e: IOException) {
                Log.w(TAG, "${upload.id} : ${e.message}")
                retry = true
            }
        }
        // Un envoi a échoué, ou la page en a ajouté un pendant ce tour.
        return if (retry || VideoQueue.pending(applicationContext).isNotEmpty()) Result.retry() else Result.success()
    }

    private fun send(upload: VideoQueue.Upload) {
        val api = Api(upload.server, upload.token, upload.accountId)
        val size = upload.file.length()
        val buffer = ByteArray(BLOCK)
        var offset = 0L
        var stuck = 0
        RandomAccessFile(upload.file, "r").use { input ->
            while (offset < size) {
                if (isStopped) throw IOException("arrêté")
                input.seek(offset)
                val length = input.read(buffer)
                if (length <= 0) throw IOException("lecture impossible à $offset")
                val before = offset
                offset = api.putBlock(upload.id, offset, buffer, length)
                VideoQueue.sent[upload.id] = offset
                // Le serveur ne suit plus : on réessaiera au prochain tour.
                if (offset <= before && ++stuck > 5) throw IOException("envoi bloqué à $offset")
            }
        }
    }

    override suspend fun getForegroundInfo(): ForegroundInfo = foregroundInfo()

    private fun foregroundInfo(): ForegroundInfo {
        val manager = applicationContext.getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(
            NotificationChannel(CHANNEL, "Envoi des vidéos", NotificationManager.IMPORTANCE_LOW)
                .apply { setShowBadge(false) },
        )
        val open = PendingIntent.getActivity(
            applicationContext,
            0,
            Intent(applicationContext, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE,
        )
        val notification: Notification = Notification.Builder(applicationContext, CHANNEL)
            .setSmallIcon(R.drawable.ic_camera)
            .setContentTitle(applicationContext.getString(R.string.app_name))
            .setContentText("Envoi de la vidéo…")
            .setContentIntent(open)
            .setOngoing(true)
            .build()
        return ForegroundInfo(NOTIFICATION, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC)
    }

    companion object {
        private const val TAG = "UploadWorker"
        private const val CHANNEL = "envois-video"
        private const val NOTIFICATION = 2
        private const val BLOCK = 4 * 1024 * 1024
    }
}
