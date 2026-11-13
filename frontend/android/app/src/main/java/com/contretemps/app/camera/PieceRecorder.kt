package com.contretemps.app.camera

import android.annotation.SuppressLint
import android.content.Context
import android.graphics.ImageFormat
import android.hardware.camera2.CameraCaptureSession
import android.hardware.camera2.CameraCharacteristics
import android.hardware.camera2.CameraDevice
import android.hardware.camera2.CameraManager
import android.hardware.camera2.CaptureRequest
import android.hardware.display.DisplayManager
import android.media.ImageReader
import android.media.MediaRecorder
import android.os.Build
import android.os.Handler
import android.util.Log
import android.util.Range
import android.util.Size
import android.view.Display
import android.view.Surface
import java.io.File

/**
 * Filme une séance en morceaux d'environ 2 minutes, sans trou entre eux
 * (MediaRecorder.setNextOutputFile). Chaque morceau fini est marqué par un
 * fichier `.done` à côté ; le dernier aussi par `.last`. L'envoi est fait à
 * part (Uploader), pour que le film ne s'arrête jamais à cause du réseau.
 *
 * Fichiers : `<dossier>/<séance>_<position>.mp4`.
 */
class PieceRecorder(
    private val context: Context,
    private val folder: File,
    private val sessionId: Int,
    private var position: Int,
    private val handler: Handler,
    /** Appelé à chaque nouveau morceau avec la position suivante, à garder si le service redémarre. */
    private val onPosition: (Int) -> Unit,
    /** Appelé quand un morceau est fini (pour l'envoyer tout de suite). */
    private val onPiece: () -> Unit,
    /** Appelé si la caméra lâche en cours de route (appel, autre appli...). */
    private val onError: (String) -> Unit,
) {
    private var camera: CameraDevice? = null
    private var session: CameraCaptureSession? = null
    private var request: CaptureRequest.Builder? = null
    private var recorder: MediaRecorder? = null
    private var current: File? = null
    private var next: File? = null
    /** Une petite image chaque seconde pendant le film (Seb, 13/11 : l'écran était noir). */
    private var reader: ImageReader? = null
    private val snapTask = object : Runnable {
        override fun run() {
            snap()
            handler.postDelayed(this, SNAP_MS)
        }
    }

    @SuppressLint("MissingPermission")
    fun start() {
        val manager = context.getSystemService(CameraManager::class.java)
        val id = manager.cameraIdList.first {
            manager.getCameraCharacteristics(it).get(CameraCharacteristics.LENS_FACING) == CameraCharacteristics.LENS_FACING_BACK
        }
        val characteristics = manager.getCameraCharacteristics(id)
        val size = videoSize(characteristics)
        val media = if (Build.VERSION.SDK_INT >= 31) MediaRecorder(context) else @Suppress("DEPRECATION") MediaRecorder()
        media.setAudioSource(MediaRecorder.AudioSource.CAMCORDER)
        media.setVideoSource(MediaRecorder.VideoSource.SURFACE)
        media.setOutputFormat(MediaRecorder.OutputFormat.MPEG_4)
        media.setVideoEncoder(MediaRecorder.VideoEncoder.H264)
        media.setAudioEncoder(MediaRecorder.AudioEncoder.AAC)
        media.setVideoSize(size.width, size.height)
        media.setVideoFrameRate(FPS)
        media.setVideoEncodingBitRate(VIDEO_BITRATE)
        media.setAudioEncodingBitRate(128_000)
        media.setAudioSamplingRate(44_100)
        media.setOrientationHint(orientation(characteristics))
        media.setMaxFileSize(PIECE_BYTES)
        current = newFile()
        media.setOutputFile(current)
        media.setOnInfoListener { _, what, _ -> onInfo(what) }
        media.setOnErrorListener { _, what, _ -> onError("Erreur d'enregistrement ($what)") }
        media.prepare()
        recorder = media

        val snapSize = snapSize(characteristics)
        val jpegOrientation = orientation(characteristics)
        manager.openCamera(id, object : CameraDevice.StateCallback() {
            override fun onOpened(device: CameraDevice) {
                camera = device
                configure(device, media, snapSize, jpegOrientation)
            }

            override fun onDisconnected(device: CameraDevice) = onError("Caméra prise par une autre appli")
            override fun onError(device: CameraDevice, error: Int) = onError("Erreur de caméra ($error)")
        }, handler)
    }

    /** Ouvre la prise de vue ; si le téléphone refuse la petite image en plus, filme sans elle. */
    private fun configure(device: CameraDevice, media: MediaRecorder, snapSize: Size?, jpegOrientation: Int) {
        val snaps = snapSize?.let { ImageReader.newInstance(it.width, it.height, ImageFormat.JPEG, 2) }
        snaps?.setOnImageAvailableListener({ r ->
            val image = try { r.acquireLatestImage() } catch (e: Exception) { null } ?: return@setOnImageAvailableListener
            try {
                val buffer = image.planes[0].buffer
                RecorderService.image = ByteArray(buffer.remaining()).also { buffer.get(it) }
            } finally {
                image.close()
            }
        }, handler)
        val targets = listOfNotNull(media.surface, snaps?.surface)
        @Suppress("DEPRECATION")
        device.createCaptureSession(targets, object : CameraCaptureSession.StateCallback() {
            override fun onConfigured(capture: CameraCaptureSession) {
                session = capture
                reader = snaps
                val request = device.createCaptureRequest(CameraDevice.TEMPLATE_RECORD).apply {
                    addTarget(media.surface)
                    set(CaptureRequest.CONTROL_AE_TARGET_FPS_RANGE, Range(FPS, FPS))
                    set(CaptureRequest.JPEG_ORIENTATION, jpegOrientation)
                    set(CaptureRequest.JPEG_QUALITY, 60.toByte())
                }
                this@PieceRecorder.request = request
                capture.setRepeatingRequest(request.build(), null, handler)
                media.start()
                // Le film commence : la lampe s'allume une seconde, pour que
                // les combattants le voient (Seb, 13/11).
                flash(FLASH_MS)
                if (snaps != null) handler.postDelayed(snapTask, SNAP_MS)
            }

            override fun onConfigureFailed(capture: CameraCaptureSession) {
                snaps?.close()
                if (snaps != null) configure(device, media, null, jpegOrientation) else onError("Caméra indisponible")
            }
        }, handler)
    }

    /** Une image du film, en plus de la vidéo (mêmes réglages, lampe comprise). */
    private fun snap() {
        val capture = session ?: return
        val builder = request ?: return
        val target = reader?.surface ?: return
        try {
            builder.addTarget(target)
            val still = builder.build()
            builder.removeTarget(target)
            capture.capture(still, null, handler)
        } catch (e: Exception) {
            builder.removeTarget(target)
            Log.w(TAG, "snap", e)
        }
    }

    /** Allume la lampe [ms] millisecondes pendant le film, si le téléphone en a une. */
    fun flash(ms: Long) {
        val capture = session ?: return
        val builder = request ?: return
        try {
            builder.set(CaptureRequest.FLASH_MODE, CaptureRequest.FLASH_MODE_TORCH)
            capture.setRepeatingRequest(builder.build(), null, handler)
            handler.postDelayed({
                if (session !== capture) return@postDelayed
                builder.set(CaptureRequest.FLASH_MODE, CaptureRequest.FLASH_MODE_OFF)
                try {
                    capture.setRepeatingRequest(builder.build(), null, handler)
                } catch (e: Exception) {
                    Log.w(TAG, "flash off", e)
                }
            }, ms)
        } catch (e: Exception) {
            Log.w(TAG, "flash", e)
        }
    }

    /** Arrête le film ; [last] : le morceau en cours est le dernier de la séance. */
    fun stop(last: Boolean) {
        val media = recorder
        recorder = null
        try {
            media?.stop()
        } catch (e: RuntimeException) {
            // Arrêté avant la première image : le fichier est vide.
            Log.w(TAG, "stop", e)
        }
        media?.release()
        handler.removeCallbacks(snapTask)
        session?.close()
        reader?.close()
        reader = null
        RecorderService.image = null
        camera?.close()
        request = null
        session = null
        camera = null
        next?.let { if (!it.exists() || it.length() == 0L) it.delete() }
        current?.let { finish(it, last) }
        current = null
        next = null
    }

    private fun onInfo(what: Int) {
        when (what) {
            MediaRecorder.MEDIA_RECORDER_INFO_MAX_FILESIZE_APPROACHING -> {
                val file = newFile()
                recorder?.setNextOutputFile(file)
                next = file
            }
            MediaRecorder.MEDIA_RECORDER_INFO_NEXT_OUTPUT_FILE_STARTED -> {
                current?.let { finish(it, last = false) }
                current = next
                next = null
            }
        }
    }

    private fun newFile(): File {
        val file = File(folder, "${sessionId}_${position++}.mp4")
        onPosition(position)
        return file
    }

    private fun finish(file: File, last: Boolean) {
        if (last) File(folder, "${file.nameWithoutExtension}.last").createNewFile()
        File(folder, "${file.nameWithoutExtension}.done").createNewFile()
        onPiece()
    }

    /** 1080p si la caméra sait, sinon la plus grande taille en 16/9 en dessous. */
    private fun videoSize(characteristics: CameraCharacteristics): Size {
        val sizes = characteristics.get(CameraCharacteristics.SCALER_STREAM_CONFIGURATION_MAP)!!
            .getOutputSizes(MediaRecorder::class.java)
        return sizes.filter { it.width <= 1920 && it.height <= 1080 && it.width * 9 == it.height * 16 }
            .maxByOrNull { it.width } ?: sizes.minBy { it.width }
    }

    /** La petite image : 640 de large en 16/9 si possible. */
    private fun snapSize(characteristics: CameraCharacteristics): Size? {
        val sizes = characteristics.get(CameraCharacteristics.SCALER_STREAM_CONFIGURATION_MAP)
            ?.getOutputSizes(ImageFormat.JPEG) ?: return null
        return sizes.filter { it.width <= 640 && it.width * 9 == it.height * 16 }.maxByOrNull { it.width }
            ?: sizes.minByOrNull { it.width * it.height }
    }

    /** Le téléphone est fixé en paysage : on tourne la vidéo comme l'écran. */
    private fun orientation(characteristics: CameraCharacteristics): Int {
        val sensor = characteristics.get(CameraCharacteristics.SENSOR_ORIENTATION) ?: 90
        val display = context.getSystemService(DisplayManager::class.java).getDisplay(Display.DEFAULT_DISPLAY)
        val degrees = when (display?.rotation) {
            Surface.ROTATION_90 -> 90
            Surface.ROTATION_180 -> 180
            Surface.ROTATION_270 -> 270
            else -> 0
        }
        return (sensor - degrees + 360) % 360
    }

    companion object {
        private const val TAG = "PieceRecorder"
        const val FPS = 30
        const val SNAP_MS = 1_000L
        // 4 Mbit/s vidéo + 128 kbit/s son : environ 62 Mo pour 2 minutes.
        const val VIDEO_BITRATE = 4_000_000
        const val PIECE_BYTES = 62L * 1024 * 1024
        const val FLASH_MS = 1_000L
    }
}
