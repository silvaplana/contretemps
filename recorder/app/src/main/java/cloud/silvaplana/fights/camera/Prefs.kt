package cloud.silvaplana.fights.camera

import android.content.Context

/** Réglages gardés sur le téléphone : l'adresse du serveur et le jeton du jumelage. */
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
        // L'API de Contretemps en ligne (docker-compose.yml : VITE_API_URL du frontend).
        const val DEFAULT_SERVER = "https://silvaplana.cloud/contretemps/api"
    }
}
