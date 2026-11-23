package com.contretemps.app.uploads

import android.content.Context
import androidx.work.Constraints
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import org.json.JSONObject
import java.io.File
import java.util.concurrent.ConcurrentHashMap

/**
 * La file d'envoi des vidéos du module Vidéos (Seb, 23/11 : « il faut que ce
 * module soit béton de chez béton »). La page écrit la vidéo ici
 * (VideoUploadsPlugin.enqueue/append/commit), puis c'est Android qui l'envoie
 * (UploadWorker) : l'envoi continue appli fermée et repart tout seul au
 * retour du réseau ou après un redémarrage du téléphone.
 *
 * Un envoi = deux fichiers dans `<filesDir>/video-uploads/` :
 * `<uploadId>.bin` la vidéo, `<uploadId>.meta` où l'envoyer. Le `.meta`
 * n'existe qu'une fois la vidéo écrite en entier (commit) : un envoi
 * interrompu pendant l'écriture n'est donc jamais envoyé à moitié.
 */
object VideoQueue {

    const val WORK = "envoi-videos"

    data class Upload(val id: String, val file: File, val server: String, val token: String?, val accountId: String?)

    /** Octets déjà chez le serveur, par envoi — pour la barre de la page (plugin `state`). */
    val sent = ConcurrentHashMap<String, Long>()

    fun folder(context: Context): File =
        File(context.filesDir, "video-uploads").apply { mkdirs() }

    fun bin(context: Context, uploadId: String) = File(folder(context), "$uploadId.bin")

    private fun meta(context: Context, uploadId: String) = File(folder(context), "$uploadId.meta")

    /** Vidéo écrite en entier : on note où l'envoyer et on lance la tâche de fond. */
    fun commit(context: Context, uploadId: String, server: String, token: String?, accountId: String?) {
        meta(context, uploadId).writeText(
            JSONObject()
                .put("server", server)
                .put("token", token ?: JSONObject.NULL)
                .put("accountId", accountId ?: JSONObject.NULL)
                .toString(),
        )
        start(context)
    }

    /** Les envois qui attendent, le plus ancien d'abord. */
    fun pending(context: Context): List<Upload> =
        (folder(context).listFiles() ?: emptyArray())
            .filter { it.extension == "meta" }
            .sortedBy { it.lastModified() }
            .mapNotNull { file ->
                val id = file.nameWithoutExtension
                val video = bin(context, id)
                if (!video.exists()) {
                    file.delete()
                    return@mapNotNull null
                }
                val json = try {
                    JSONObject(file.readText())
                } catch (e: Exception) {
                    file.delete()
                    return@mapNotNull null
                }
                Upload(
                    id = id,
                    file = video,
                    server = json.optString("server"),
                    token = json.optString("token").takeIf { it.isNotEmpty() && it != "null" },
                    accountId = json.optString("accountId").takeIf { it.isNotEmpty() && it != "null" },
                )
            }

    /** Envoi fini (ou refusé) : la vidéo quitte le téléphone. */
    fun forget(context: Context, uploadId: String) {
        bin(context, uploadId).delete()
        meta(context, uploadId).delete()
        sent.remove(uploadId)
    }

    /**
     * Une vidéo à moitié écrite (appli tuée pendant `append`) ne sera jamais
     * envoyée, faute de `.meta` : elle ne doit pas occuper le téléphone pour
     * toujours. Au-delà de six heures, elle part.
     */
    private fun sweep(context: Context) {
        val vieux = System.currentTimeMillis() - 6 * 60 * 60 * 1000
        for (file in folder(context).listFiles() ?: emptyArray()) {
            if (file.extension != "bin" || file.lastModified() > vieux) continue
            if (!File(folder(context), "${file.nameWithoutExtension}.meta").exists()) file.delete()
        }
    }

    /**
     * Une seule tâche à la fois (KEEP) : si elle tourne déjà, elle verra le
     * nouvel envoi en relisant la file. Avec réseau seulement, et reprise
     * automatique après un redémarrage du téléphone (WorkManager).
     */
    fun start(context: Context) {
        sweep(context)
        WorkManager.getInstance(context).enqueueUniqueWork(
            WORK,
            ExistingWorkPolicy.KEEP,
            OneTimeWorkRequestBuilder<UploadWorker>()
                .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
                .build(),
        )
    }
}
