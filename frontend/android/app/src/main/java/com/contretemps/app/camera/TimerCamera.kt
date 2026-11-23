package com.contretemps.app.camera

import android.annotation.SuppressLint
import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.ImageFormat
import android.graphics.Matrix
import android.graphics.Rect
import android.graphics.YuvImage
import android.hardware.camera2.CameraCaptureSession
import android.hardware.camera2.CameraCharacteristics
import android.hardware.camera2.CameraDevice
import android.hardware.camera2.CameraManager
import android.hardware.camera2.CaptureRequest
import android.hardware.display.DisplayManager
import android.media.Image
import android.media.ImageReader
import android.media.MediaRecorder
import android.os.Build
import android.os.Handler
import android.os.HandlerThread
import android.os.SystemClock
import android.util.Log
import android.util.Range
import android.util.Size
import android.view.Display
import android.view.Surface
import com.contretemps.app.uploads.VideoQueue
import java.io.ByteArrayOutputStream
import java.io.File

/**
 * La caméra du Timer étendu de Fights, filmée par l'appli (Seb, 23/11 :
 * « que Tournage caméra et Timer utilisent les mêmes technos ») : mêmes
 * réglages que la caméra de Tournage (PieceRecorder : 1080p, 30 images/s,
 * 4 Mbit/s), mais un seul fichier par combat, rangé dans le dossier de la
 * file d'envoi (VideoQueue) pour partir de là sans copie.
 *
 * L'image de la miniature : une petite image (640 px, ~5 par seconde),
 * relue par la page (TournagePlugin.timerFrame). La lampe : allumée ou
 * éteinte à la demande, film ou pas.
 */
object TimerCamera {

    private const val TAG = "TimerCamera"
    private const val FRAME_MS = 200L

    private var thread: HandlerThread? = null
    private var handler: Handler? = null
    private var camera: CameraDevice? = null
    private var session: CameraCaptureSession? = null
    private var request: CaptureRequest.Builder? = null
    private var preview: ImageReader? = null
    private var recorder: MediaRecorder? = null
    private var file: File? = null
    private var characteristics: CameraCharacteristics? = null
    private var lastFrame = 0L
    private var light = false

    @Volatile var frame: ByteArray? = null
        private set
    @Volatile var error: String? = null
        private set
    val open get() = camera != null
    val recording get() = recorder != null

    /** Ouvre la caméra arrière, sans filmer : l'image de la miniature et la lampe. */
    @SuppressLint("MissingPermission")
    fun open(context: Context) {
        if (thread != null) return
        error = null
        val t = HandlerThread("timer-camera").apply { start() }
        thread = t
        val h = Handler(t.looper)
        handler = h
        val manager = context.getSystemService(CameraManager::class.java)
        val id = manager.cameraIdList.firstOrNull {
            manager.getCameraCharacteristics(it).get(CameraCharacteristics.LENS_FACING) == CameraCharacteristics.LENS_FACING_BACK
        } ?: return fail("Pas de caméra arrière")
        val chars = manager.getCameraCharacteristics(id)
        characteristics = chars
        val size = previewSize(chars)
        val reader = ImageReader.newInstance(size.width, size.height, ImageFormat.YUV_420_888, 2)
        reader.setOnImageAvailableListener({ r ->
            val image = try { r.acquireLatestImage() } catch (e: Exception) { null } ?: return@setOnImageAvailableListener
            try {
                val now = SystemClock.elapsedRealtime()
                if (now - lastFrame >= FRAME_MS) {
                    lastFrame = now
                    frame = jpeg(image, rotation(context))
                }
            } catch (e: Exception) {
                Log.w(TAG, "frame", e)
            } finally {
                image.close()
            }
        }, h)
        preview = reader
        try {
            manager.openCamera(id, object : CameraDevice.StateCallback() {
                override fun onOpened(device: CameraDevice) {
                    camera = device
                    configure(listOf(reader.surface))
                }

                override fun onDisconnected(device: CameraDevice) {
                    fail("Caméra prise par une autre appli")
                }

                override fun onError(device: CameraDevice, code: Int) {
                    fail("Erreur de caméra ($code)")
                }
            }, h)
        } catch (e: Exception) {
            fail("Caméra indisponible")
        }
    }

    /** Commence le film du combat, dans un nouveau fichier de la file d'envoi. */
    fun record(context: Context): Boolean {
        if (camera == null) return false
        val chars = characteristics ?: return false
        if (recorder != null) return true
        val size = videoSize(chars)
        val target = File(VideoQueue.folder(context), "film-${System.currentTimeMillis()}.mp4")
        val media = if (Build.VERSION.SDK_INT >= 31) MediaRecorder(context) else @Suppress("DEPRECATION") MediaRecorder()
        try {
            media.setAudioSource(MediaRecorder.AudioSource.CAMCORDER)
            media.setVideoSource(MediaRecorder.VideoSource.SURFACE)
            media.setOutputFormat(MediaRecorder.OutputFormat.MPEG_4)
            media.setVideoEncoder(MediaRecorder.VideoEncoder.H264)
            media.setAudioEncoder(MediaRecorder.AudioEncoder.AAC)
            media.setVideoSize(size.width, size.height)
            media.setVideoFrameRate(PieceRecorder.FPS)
            media.setVideoEncodingBitRate(PieceRecorder.VIDEO_BITRATE)
            media.setAudioEncodingBitRate(128_000)
            media.setAudioSamplingRate(44_100)
            media.setOrientationHint(videoRotation(context, chars))
            media.setOutputFile(target)
            media.prepare()
        } catch (e: Exception) {
            Log.w(TAG, "record", e)
            media.release()
            return false
        }
        recorder = media
        file = target
        configure(listOfNotNull(media.surface, preview?.surface)) { media.start() }
        return true
    }

    fun pause(on: Boolean) {
        val media = recorder ?: return
        try {
            if (on) media.pause() else media.resume()
        } catch (e: Exception) {
            Log.w(TAG, "pause", e)
        }
    }

    /** Arrête le film ; le fichier du combat, ou null si rien n'a été filmé. */
    fun stop(): File? {
        val media = recorder ?: return null
        recorder = null
        val done = file
        file = null
        var ok = true
        try {
            media.stop()
        } catch (e: RuntimeException) {
            // Arrêté avant la première image : le fichier est vide.
            ok = false
        }
        media.release()
        preview?.surface?.let { configure(listOf(it)) }
        if (!ok || done == null || done.length() == 0L) {
            done?.delete()
            return null
        }
        return done
    }

    fun light(on: Boolean) {
        light = on
        val capture = session ?: return
        val builder = request ?: return
        try {
            builder.set(CaptureRequest.FLASH_MODE, if (on) CaptureRequest.FLASH_MODE_TORCH else CaptureRequest.FLASH_MODE_OFF)
            capture.setRepeatingRequest(builder.build(), null, handler)
        } catch (e: Exception) {
            Log.w(TAG, "light", e)
        }
    }

    /** Ferme tout ; un film en cours est jeté. */
    fun close() {
        recorder?.let {
            try { it.stop() } catch (e: RuntimeException) { /* rien de filmé */ }
            it.release()
        }
        recorder = null
        file?.delete()
        file = null
        try { session?.close() } catch (e: Exception) { /* déjà fermée */ }
        session = null
        request = null
        camera?.close()
        camera = null
        preview?.close()
        preview = null
        frame = null
        light = false
        thread?.quitSafely()
        thread = null
        handler = null
    }

    private fun fail(message: String) {
        Log.w(TAG, message)
        error = message
        close()
        error = message
    }

    private fun configure(targets: List<Surface>, then: (() -> Unit)? = null) {
        val device = camera ?: return
        try { session?.close() } catch (e: Exception) { /* déjà fermée */ }
        session = null
        @Suppress("DEPRECATION")
        device.createCaptureSession(targets, object : CameraCaptureSession.StateCallback() {
            override fun onConfigured(capture: CameraCaptureSession) {
                if (camera !== device) return capture.close()
                session = capture
                val builder = device.createCaptureRequest(
                    if (targets.size > 1) CameraDevice.TEMPLATE_RECORD else CameraDevice.TEMPLATE_PREVIEW,
                ).apply {
                    targets.forEach { addTarget(it) }
                    set(CaptureRequest.CONTROL_AE_TARGET_FPS_RANGE, Range(PieceRecorder.FPS, PieceRecorder.FPS))
                    set(CaptureRequest.FLASH_MODE, if (light) CaptureRequest.FLASH_MODE_TORCH else CaptureRequest.FLASH_MODE_OFF)
                }
                request = builder
                try {
                    capture.setRepeatingRequest(builder.build(), null, handler)
                    then?.invoke()
                } catch (e: Exception) {
                    fail("Caméra indisponible")
                }
            }

            override fun onConfigureFailed(capture: CameraCaptureSession) {
                fail("Caméra indisponible")
            }
        }, handler)
    }

    /** Comme PieceRecorder : 1080p si la caméra sait, sinon la plus grande taille en 16/9 en dessous. */
    private fun videoSize(chars: CameraCharacteristics): Size {
        val sizes = chars.get(CameraCharacteristics.SCALER_STREAM_CONFIGURATION_MAP)!!.getOutputSizes(MediaRecorder::class.java)
        return sizes.filter { it.width <= 1920 && it.height <= 1080 && it.width * 9 == it.height * 16 }
            .maxByOrNull { it.width } ?: sizes.minBy { it.width }
    }

    private fun previewSize(chars: CameraCharacteristics): Size {
        val sizes = chars.get(CameraCharacteristics.SCALER_STREAM_CONFIGURATION_MAP)!!.getOutputSizes(ImageFormat.YUV_420_888)
        return sizes.filter { it.width <= 640 && it.width * 9 == it.height * 16 }.maxByOrNull { it.width }
            ?: sizes.minBy { it.width * it.height }
    }

    /** Le sens de l'écran (figé par le Timer au premier coup de cloche). */
    private fun displayDegrees(context: Context): Int {
        val display = context.getSystemService(DisplayManager::class.java).getDisplay(Display.DEFAULT_DISPLAY)
        return when (display?.rotation) {
            Surface.ROTATION_90 -> 90
            Surface.ROTATION_180 -> 180
            Surface.ROTATION_270 -> 270
            else -> 0
        }
    }

    private fun videoRotation(context: Context, chars: CameraCharacteristics): Int {
        val sensor = chars.get(CameraCharacteristics.SENSOR_ORIENTATION) ?: 90
        return (sensor - displayDegrees(context) + 360) % 360
    }

    private fun rotation(context: Context): Int = characteristics?.let { videoRotation(context, it) } ?: 0

    /** Une image YUV en JPEG, tournée dans le sens de l'écran. */
    private fun jpeg(image: Image, degrees: Int): ByteArray {
        val out = ByteArrayOutputStream()
        YuvImage(nv21(image), ImageFormat.NV21, image.width, image.height, null)
            .compressToJpeg(Rect(0, 0, image.width, image.height), 70, out)
        if (degrees == 0) return out.toByteArray()
        val bitmap = BitmapFactory.decodeByteArray(out.toByteArray(), 0, out.size())
        val turned = Bitmap.createBitmap(bitmap, 0, 0, bitmap.width, bitmap.height, Matrix().apply { postRotate(degrees.toFloat()) }, false)
        bitmap.recycle()
        val result = ByteArrayOutputStream()
        turned.compress(Bitmap.CompressFormat.JPEG, 70, result)
        turned.recycle()
        return result.toByteArray()
    }

    private fun nv21(image: Image): ByteArray {
        val width = image.width
        val height = image.height
        val out = ByteArray(width * height * 3 / 2)
        val y = image.planes[0]
        var pos = 0
        for (row in 0 until height) {
            val buffer = y.buffer
            for (col in 0 until width) {
                out[pos++] = buffer.get(row * y.rowStride + col * y.pixelStride)
            }
        }
        val u = image.planes[1]
        val v = image.planes[2]
        for (row in 0 until height / 2) {
            for (col in 0 until width / 2) {
                out[pos++] = v.buffer.get(row * v.rowStride + col * v.pixelStride)
                out[pos++] = u.buffer.get(row * u.rowStride + col * u.pixelStride)
            }
        }
        return out
    }
}
