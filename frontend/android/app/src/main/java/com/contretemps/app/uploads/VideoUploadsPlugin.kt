package com.contretemps.app.uploads

import android.util.Base64
import com.getcapacitor.JSArray
import com.getcapacitor.JSObject
import com.getcapacitor.Plugin
import com.getcapacitor.PluginCall
import com.getcapacitor.PluginMethod
import com.getcapacitor.annotation.CapacitorPlugin

/**
 * Le pont entre le module Vidéos de la page (frontend/src/utils/
 * envoisNatifs.js) et la file d'envoi d'Android (VideoQueue) : la page écrit
 * la vidéo bloc par bloc (`enqueue`, `append`, `commit`), puis Android
 * l'envoie, même appli fermée. `state` donne l'avancement pour la barre de la
 * page, `cancel` jette un envoi dont plus personne ne veut.
 */
@CapacitorPlugin(name = "EnvoisVideo")
class VideoUploadsPlugin : Plugin() {

    /** Ouvre (ou rouvre) le fichier de cet envoi sur le téléphone. */
    @PluginMethod
    fun enqueue(call: PluginCall) {
        val id = call.getString("uploadId") ?: return call.reject("uploadId")
        VideoQueue.forget(context, id)
        VideoQueue.bin(context, id).createNewFile()
        call.resolve()
    }

    /** Ajoute un bloc de la vidéo (base64) à la fin du fichier. */
    @PluginMethod
    fun append(call: PluginCall) {
        val id = call.getString("uploadId") ?: return call.reject("uploadId")
        val data = call.getString("data") ?: return call.reject("data")
        val file = VideoQueue.bin(context, id)
        if (!file.exists()) return call.reject("Envoi inconnu")
        file.appendBytes(Base64.decode(data, Base64.DEFAULT))
        call.resolve()
    }

    /** La vidéo est écrite en entier : à Android de l'envoyer. */
    @PluginMethod
    fun commit(call: PluginCall) {
        val id = call.getString("uploadId") ?: return call.reject("uploadId")
        val server = call.getString("server") ?: return call.reject("server")
        if (!VideoQueue.bin(context, id).exists()) return call.reject("Envoi inconnu")
        VideoQueue.commit(context, id, server, call.getString("token"), call.getString("accountId"))
        call.resolve()
    }

    /** Ce qui attend encore, avec les octets déjà chez le serveur. */
    @PluginMethod
    fun state(call: PluginCall) {
        val uploads = JSArray()
        for (upload in VideoQueue.pending(context)) {
            uploads.put(
                JSObject().apply {
                    put("uploadId", upload.id)
                    put("size", upload.file.length())
                    put("sent", VideoQueue.sent[upload.id] ?: 0L)
                },
            )
        }
        call.resolve(JSObject().apply { put("uploads", uploads) })
    }

    @PluginMethod
    fun cancel(call: PluginCall) {
        val id = call.getString("uploadId") ?: return call.reject("uploadId")
        VideoQueue.forget(context, id)
        call.resolve()
    }
}
