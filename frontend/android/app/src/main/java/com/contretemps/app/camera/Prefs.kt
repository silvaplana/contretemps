package com.contretemps.app.camera

import android.content.Context

/** Réglages gardés sur le téléphone : l'adresse de l'API et le jeton de la caméra (TournagePlugin.start). */
class Prefs(context: Context) {
    private val prefs = context.getSharedPreferences("camera", Context.MODE_PRIVATE)

    var server: String
        get() = prefs.getString("server", DEFAULT_SERVER) ?: DEFAULT_SERVER
        set(value) = prefs.edit().putString("server", value.trim()).apply()

    var token: String?
        get() = prefs.getString("token", null)
        set(value) = prefs.edit().putString("token", value).apply()

    fun int(key: String): Int = prefs.getInt(key, 0)

    fun setInt(key: String, value: Int) {
        prefs.edit().putInt(key, value).commit()
    }

    companion object {
        // Remplacée par l'adresse de l'API de l'école dès que Tournage passe sur « Caméra ».
        const val DEFAULT_SERVER = "https://silvaplana.cloud/contretemps/api"
    }
}
