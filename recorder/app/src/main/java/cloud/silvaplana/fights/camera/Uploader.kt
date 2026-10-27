package cloud.silvaplana.fights.camera

import android.util.Log
import java.io.File
import java.io.IOException
import java.io.RandomAccessFile

/**
 * Envoie les morceaux finis (`.done`) au serveur, dans l'ordre, par blocs de
 * 4 Mo. Une coupure de réseau n'est pas grave : le morceau reste sur le
 * téléphone et l'envoi reprend là où le serveur s'est arrêté. Un morceau
 * envoyé est effacé du téléphone.
 */
class Uploader(private val folder: File) {

    /** Les morceaux finis pas encore envoyés, dans l'ordre de la séance. */
    fun pending(): List<File> =
        (folder.listFiles() ?: emptyArray())
            .filter { it.extension == "mp4" && File(folder, "${it.nameWithoutExtension}.done").exists() }
            .sortedWith(compareBy({ ids(it).first }, { ids(it).second }))

    /** Envoie tout ce qui attend ; s'arrête à la première coupure. */
    fun sendAll(api: Api) {
        for (file in pending()) {
            try {
                send(api, file)
                forget(file)
            } catch (e: Api.Error) {
                if (e.status == 404) {
                    // Séance effacée dans Fights entre-temps : plus personne n'attend ce morceau.
                    Log.w(TAG, "${file.name} : ${e.message}")
                    forget(file)
                } else {
                    Log.w(TAG, "${file.name} : ${e.status} ${e.message}")
                    return
                }
            } catch (e: IOException) {
                Log.w(TAG, "${file.name} : ${e.message}")
                return
            }
        }
    }

    private fun send(api: Api, file: File) {
        val size = file.length()
        if (size == 0L) return
        val (sessionId, position) = ids(file)
        val last = File(folder, "${file.nameWithoutExtension}.last").exists()
        var piece = api.openPiece(sessionId, position, size, last)
        var offset = piece.received
        val buffer = ByteArray(BLOCK)
        var stuck = 0
        RandomAccessFile(file, "r").use { input ->
            while (offset < size) {
                input.seek(offset)
                val length = input.read(buffer)
                val before = offset
                offset = try {
                    api.putBlock(piece.uploadId, offset, buffer, length)
                } catch (e: Api.Error) {
                    if (e.status != 404) throw e
                    // Envoi abandonné et nettoyé par le serveur : on le rouvre.
                    piece = api.openPiece(sessionId, position, size, last)
                    piece.received
                }
                // Le serveur ne suit plus : on réessaiera au prochain tour.
                if (offset <= before && ++stuck > 5) throw IOException("envoi bloqué à $offset")
            }
        }
    }

    private fun forget(file: File) {
        File(folder, "${file.nameWithoutExtension}.done").delete()
        File(folder, "${file.nameWithoutExtension}.last").delete()
        file.delete()
    }

    private fun ids(file: File): Pair<Int, Int> {
        val (session, position) = file.nameWithoutExtension.split("_")
        return session.toInt() to position.toInt()
    }

    companion object {
        private const val TAG = "Uploader"
        private const val BLOCK = 4 * 1024 * 1024
    }
}
