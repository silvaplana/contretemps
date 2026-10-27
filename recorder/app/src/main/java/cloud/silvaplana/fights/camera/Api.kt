package cloud.silvaplana.fights.camera

import org.json.JSONObject
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL

/**
 * Le serveur de Fights (backend/src/session_clips/receiver.py, routes
 * `/session-clips/recorder/...`). Le téléphone n'a pas de compte : il se
 * présente avec le jeton reçu au jumelage (en-tête X-Recorder-Token).
 */
class Api(private val server: String, private val token: String?) {

    class Error(val status: Int, message: String) : IOException(message)

    /** Ce que le serveur demande : filmer la séance [sessionId] (null = rester prêt). */
    data class Orders(val sessionId: Int?, val signal: String)

    data class PieceState(val uploadId: String, val received: Long)

    fun pair(code: String): String =
        call("POST", "/session-clips/recorder/pair", JSONObject().put("code", code)).getString("token")

    fun heartbeat(recording: Boolean, battery: Int?, freeBytes: Long, pending: Int): Orders {
        val body = JSONObject()
            .put("state", if (recording) "recording" else "ready")
            .put("battery_percent", battery ?: JSONObject.NULL)
            .put("free_bytes", freeBytes)
            .put("pending_pieces", pending)
        val answer = call("POST", "/session-clips/recorder/heartbeat", body)
        val session = if (answer.isNull("session_id")) null else answer.getInt("session_id")
        return Orders(session, answer.optString("signal", "beep"))
    }

    /** Ouvre (ou rouvre après une coupure) l'envoi d'un morceau. */
    fun openPiece(sessionId: Int, position: Int, size: Long, last: Boolean): PieceState {
        val body = JSONObject()
            .put("session_id", sessionId)
            .put("position", position)
            .put("size", size)
            .put("last", last)
        return piece(call("POST", "/session-clips/recorder/pieces", body))
    }

    /** Envoie un bloc à la position [offset] ; renvoie ce que le serveur a reçu en tout. */
    fun putBlock(uploadId: String, offset: Long, data: ByteArray, length: Int): Long {
        val connection = open("PUT", "/session-clips/recorder/pieces/$uploadId")
        connection.setRequestProperty("Content-Type", "application/octet-stream")
        connection.setRequestProperty("X-Decalage", offset.toString())
        connection.setFixedLengthStreamingMode(length)
        connection.doOutput = true
        connection.outputStream.use { it.write(data, 0, length) }
        val status = connection.responseCode
        if (status == 409) {
            // Le serveur n'est pas au même endroit (bloc perdu ou rejoué) : on repart de sa position.
            val detail = JSONObject(read(connection, error = true)).getJSONObject("detail")
            return detail.getLong("octets_recus")
        }
        if (status !in 200..299) throw Error(status, read(connection, error = true))
        return piece(JSONObject(read(connection))).received
    }

    private fun piece(json: JSONObject) = PieceState(json.getString("upload_id"), json.getLong("received"))

    private fun call(method: String, path: String, body: JSONObject): JSONObject {
        val connection = open(method, path)
        connection.setRequestProperty("Content-Type", "application/json")
        connection.doOutput = true
        connection.outputStream.use { it.write(body.toString().toByteArray()) }
        val status = connection.responseCode
        if (status !in 200..299) throw Error(status, read(connection, error = true))
        return JSONObject(read(connection))
    }

    private fun open(method: String, path: String): HttpURLConnection {
        val connection = URL(server.trimEnd('/') + path).openConnection() as HttpURLConnection
        connection.requestMethod = method
        connection.connectTimeout = 15_000
        connection.readTimeout = 60_000
        if (token != null) connection.setRequestProperty("X-Recorder-Token", token)
        return connection
    }

    private fun read(connection: HttpURLConnection, error: Boolean = false): String {
        val stream = if (error) connection.errorStream else connection.inputStream
        return stream?.bufferedReader()?.use { it.readText() } ?: ""
    }
}
