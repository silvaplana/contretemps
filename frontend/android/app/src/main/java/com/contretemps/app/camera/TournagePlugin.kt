package com.contretemps.app.camera

import android.Manifest
import android.annotation.SuppressLint
import android.content.Intent
import android.util.Base64
import android.net.Uri
import android.os.Build
import android.os.PowerManager
import android.provider.Settings
import com.getcapacitor.JSObject
import com.getcapacitor.Plugin
import com.getcapacitor.PluginCall
import com.getcapacitor.PluginMethod
import com.getcapacitor.PermissionState
import com.getcapacitor.annotation.CapacitorPlugin
import com.getcapacitor.annotation.Permission
import com.getcapacitor.annotation.PermissionCallback

/**
 * Le pont entre Fights › Tournage (frontend/src/modules/session-clips/
 * Tournage.jsx) et le film en tâche de fond (RecorderService) :
 * `start` (sélecteur sur « Caméra »), `stop` (« Éteint » ou
 * « Télécommande »), `status` (relu chaque seconde) et `preview` (l'image
 * de Tournage tient la caméra).
 */
@CapacitorPlugin(
    name = "Tournage",
    permissions = [
        Permission(alias = "camera", strings = [Manifest.permission.CAMERA, Manifest.permission.RECORD_AUDIO]),
    ],
)
class TournagePlugin : Plugin() {

    @PluginMethod
    fun start(call: PluginCall) {
        val prefs = Prefs(context)
        prefs.server = call.getString("server") ?: return call.reject("server")
        prefs.token = call.getString("token") ?: return call.reject("token")
        if (getPermissionState("camera") != PermissionState.GRANTED) {
            requestPermissionForAlias("camera", call, "afterPermission")
            return
        }
        launch(call)
    }

    @PermissionCallback
    private fun afterPermission(call: PluginCall) {
        if (getPermissionState("camera") != PermissionState.GRANTED) {
            call.reject("Autorisez la caméra et le micro pour filmer.")
            return
        }
        launch(call)
    }

    private fun launch(call: PluginCall) {
        if (Build.VERSION.SDK_INT >= 33) {
            activity.requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 2)
        }
        askBatteryExemption()
        RecorderService.finishing = false
        if (!RecorderService.running) RecorderService.start(context)
        call.resolve()
    }

    @PluginMethod
    fun stop(call: PluginCall) {
        // Une vidéo reste à envoyer : l'envoi continue, même hors de « Caméra » (Seb, 12/11).
        if (RecorderService.running && (RecorderService.upload?.pending()?.isNotEmpty() == true)) {
            RecorderService.finishing = true
        } else {
            Prefs(context).token = null
            context.stopService(Intent(context, RecorderService::class.java))
        }
        call.resolve()
    }

    /** Filmer / Arrêter vient d'être touché sur ce téléphone : pas d'attente. */
    @PluginMethod
    fun poke(call: PluginCall) {
        RecorderService.poke()
        call.resolve()
    }

    @PluginMethod
    fun status(call: PluginCall) {
        val s = RecorderService.status
        call.resolve(JSObject().apply {
            put("running", RecorderService.running)
            put("online", s.online)
            put("recording", s.recording)
            put("wanted", s.wanted)
            put("pending", s.pending)
            put("error", s.error)
            RecorderService.image?.takeIf { s.recording }?.let {
                put("image", "data:image/jpeg;base64," + Base64.encodeToString(it, Base64.NO_WRAP))
            }
            RecorderService.upload?.let { u ->
                u.progress?.let { put("sent", it.sent); put("size", it.size) }
                u.failure?.let { put("sendFailure", it) }
            }
        })
    }

    @PluginMethod
    fun preview(call: PluginCall) {
        RecorderService.previewing = call.getBoolean("on", false) == true
        call.resolve()
    }

    /** Samsung et d'autres coupent les applis en veille : on demande à être laissé tranquille. */
    @SuppressLint("BatteryLife")
    private fun askBatteryExemption() {
        if (context.getSystemService(PowerManager::class.java).isIgnoringBatteryOptimizations(context.packageName)) return
        try {
            activity.startActivity(Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, Uri.parse("package:${context.packageName}")))
        } catch (e: Exception) {
            // Réglage absent sur ce téléphone.
        }
    }
}
