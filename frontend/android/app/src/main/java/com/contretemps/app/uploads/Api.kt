package com.contretemps.app.uploads

import org.json.JSONObject
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL

/**
 * Le module Vidéos du serveur (backend/src/videos/receiver.py) : écrire un
 * bloc d'un envoi déjà ouvert par la page. La page passe son jeton de session
 * et son profil (comme `api/identite.js` les pose sur chaque requête).
 */
class Api(private val server: String, private val token: String?, private val accountId: String?) {

    /** Le serveur refuse cet envoi pour de bon : rien à réessayer. */
    class Refused(val status: Int, message: String) : IOException(message)

    /** Écrit un bloc à [offset] ; renvoie ce que le serveur a reçu en tout. */
    fun putBlock(uploadId: String, offset: Long, data: ByteArray, length: Int): Long {
        val connection = open("PUT", "/videos/televersements/$uploadId")
        connection.setRequestProperty("Content-Type", "application/octet-stream")
        connection.setRequestProperty("X-Decalage", offset.toString())
        connection.setFixedLengthStreamingMode(length)
        connection.doOutput = true
        connection.outputStream.use { it.write(data, 0, length) }
        val status = connection.responseCode
        if (status == 409) {
            // Décalage désynchronisé : le corps donne le VRAI décalage, on
            // repart dessus. Un autre 409 (fiche d'une nouvelle saison, voir
            // comptes/rbac.py) n'a pas ce décalage : rien à réessayer.
            val body = read(connection, error = true)
            return decalage(body) ?: throw Refused(status, body)
        }
        if (status == 408 || status == 429 || status >= 500) throw IOException("réponse $status du serveur")
        if (status !in 200..299) throw Refused(status, read(connection, error = true))
        return JSONObject(read(connection)).getLong("octets_recus")
    }

    private fun decalage(body: String): Long? = try {
        val detail = JSONObject(body).getJSONObject("detail")
        if (detail.has("octets_recus")) detail.getLong("octets_recus") else null
    } catch (e: Exception) {
        null
    }

    private fun open(method: String, path: String): HttpURLConnection {
        val connection = URL(server.trimEnd('/') + path).openConnection() as HttpURLConnection
        connection.requestMethod = method
        connection.connectTimeout = 15_000
        connection.readTimeout = 60_000
        if (token != null) connection.setRequestProperty("Authorization", "Bearer $token")
        if (accountId != null) connection.setRequestProperty("X-Compte-Id", accountId)
        return connection
    }

    private fun read(connection: HttpURLConnection, error: Boolean = false): String {
        val stream = if (error) connection.errorStream else connection.inputStream
        return stream?.bufferedReader()?.use { it.readText() } ?: ""
    }
}
