package cloud.silvaplana.fights.camera

import android.Manifest
import android.annotation.SuppressLint
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Color
import android.graphics.Matrix
import android.graphics.RectF
import android.graphics.SurfaceTexture
import android.hardware.camera2.CameraCaptureSession
import android.hardware.camera2.CameraCharacteristics
import android.hardware.camera2.CameraDevice
import android.hardware.camera2.CameraManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.PowerManager
import android.provider.Settings
import android.text.InputType
import android.util.Size
import android.util.TypedValue
import android.view.Gravity
import android.view.Surface
import android.view.TextureView
import android.view.View
import android.view.ViewGroup.LayoutParams.MATCH_PARENT
import android.view.ViewGroup.LayoutParams.WRAP_CONTENT
import android.widget.Button
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import kotlin.concurrent.thread

/**
 * L'écran du téléphone de la salle : taper le code de Fights pour le jumeler,
 * puis l'image de la caméra pour la cadrer et l'état (prête, filme, morceaux
 * à envoyer). Le film lui-même est fait par RecorderService, même écran éteint.
 */
class MainActivity : Activity() {

    private lateinit var prefs: Prefs
    private val main = Handler(Looper.getMainLooper())
    private var preview: TextureView? = null
    private var stateText: TextView? = null
    private var camera: CameraDevice? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        prefs = Prefs(this)
        askPermissions()
    }

    override fun onResume() {
        super.onResume()
        show()
        main.post(refresh)
    }

    override fun onPause() {
        main.removeCallbacks(refresh)
        closePreview()
        super.onPause()
    }

    // --- Jumelage ---

    private fun show() {
        closePreview()
        preview = null
        stateText = null
        if (prefs.token == null) showPairing() else showStatus()
    }

    private fun showPairing() {
        val code = EditText(this).apply {
            hint = "Code à 8 chiffres"
            inputType = InputType.TYPE_CLASS_NUMBER
            textSize = 28f
            gravity = Gravity.CENTER
        }
        val server = EditText(this).apply {
            setText(prefs.server)
            textSize = 14f
            inputType = InputType.TYPE_TEXT_VARIATION_URI
        }
        val message = text("", 17f)
        val pairButton = Button(this).apply {
            text = "Jumeler"
            textSize = 20f
            minHeight = dp(56)
        }
        pairButton.setOnClickListener {
            pairButton.isEnabled = false
            message.text = ""
            prefs.server = server.text.toString()
            val typed = code.text.toString()
            thread {
                val error = try {
                    prefs.token = Api(prefs.server, null).pair(typed)
                    null
                } catch (e: Api.Error) {
                    if (e.status == 404) "Code inconnu ou expiré. Affichez-en un nouveau dans Fights." else "Erreur du serveur (${e.status})."
                } catch (e: Exception) {
                    "Serveur injoignable. Vérifiez le Wi-Fi."
                }
                main.post {
                    pairButton.isEnabled = true
                    if (error != null) {
                        message.text = error
                    } else {
                        askBatteryExemption()
                        startService()
                        show()
                    }
                }
            }
        }
        setContentView(ScrollView(this).apply { addView(column(
            text("Caméra Fights", 26f),
            text("Dans Fights, touchez la pastille Caméra puis « Afficher un code », et tapez-le ici.", 17f),
            code, pairButton, message,
            text("Serveur", 14f), server,
        )) })
    }

    // --- État et image ---

    private fun showStatus() {
        val texture = TextureView(this)
        val state = text("", 20f).apply {
            setTextColor(Color.WHITE)
            setBackgroundColor(0x99000000.toInt())
            setPadding(dp(16), dp(12), dp(16), dp(12))
        }
        val frame = FrameLayout(this).apply {
            setBackgroundColor(Color.BLACK)
            addView(texture, FrameLayout.LayoutParams(MATCH_PARENT, MATCH_PARENT))
            addView(state, FrameLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT, Gravity.BOTTOM))
        }
        preview = texture
        stateText = state
        setContentView(frame)
        startService()
    }

    private val refresh = object : Runnable {
        override fun run() {
            if (prefs.token == null && preview != null) {
                show()  // remplacé par un autre téléphone
            }
            val status = RecorderService.status
            stateText?.text = describe(status)
            val canPreview = !status.recording && !status.wanted && hasPermissions()
            if (canPreview && camera == null && preview != null) openPreview()
            if (!canPreview && camera != null) closePreview()
            main.postDelayed(this, 1000)
        }
    }

    private fun describe(s: RecorderService.Status): String {
        val lines = mutableListOf<String>()
        lines += when {
            s.recording -> "● Filme · " + chrono(s.since)
            s.wanted -> "Démarrage…"
            s.online -> "Prête · attend « Démarrer la séance » dans Fights"
            else -> "Connexion au serveur…"
        }
        if (s.pending > 0) lines += "${s.pending} morceau${if (s.pending > 1) "x" else ""} à envoyer"
        s.error?.let { lines += it }
        if (!s.recording) lines += "Fixez le téléphone en paysage, toute la surface de combat dans l'image."
        return lines.joinToString("\n")
    }

    private fun chrono(since: Long?): String {
        val seconds = ((System.currentTimeMillis() - (since ?: System.currentTimeMillis())) / 1000).toInt()
        return "%02d:%02d:%02d".format(seconds / 3600, seconds / 60 % 60, seconds % 60)
    }

    @SuppressLint("MissingPermission")
    private fun openPreview() {
        val texture = preview ?: return
        if (!texture.isAvailable) {
            texture.surfaceTextureListener = object : TextureView.SurfaceTextureListener {
                override fun onSurfaceTextureAvailable(s: SurfaceTexture, w: Int, h: Int) = openPreview()
                override fun onSurfaceTextureSizeChanged(s: SurfaceTexture, w: Int, h: Int) {}
                override fun onSurfaceTextureDestroyed(s: SurfaceTexture) = true
                override fun onSurfaceTextureUpdated(s: SurfaceTexture) {}
            }
            return
        }
        val manager = getSystemService(CameraManager::class.java)
        val id = manager.cameraIdList.firstOrNull {
            manager.getCameraCharacteristics(it).get(CameraCharacteristics.LENS_FACING) == CameraCharacteristics.LENS_FACING_BACK
        } ?: return
        val size = Size(1920, 1080)
        RecorderService.previewing = true
        manager.openCamera(id, object : CameraDevice.StateCallback() {
            override fun onOpened(device: CameraDevice) {
                if (preview !== texture) {
                    device.close()
                    return
                }
                camera = device
                texture.surfaceTexture!!.setDefaultBufferSize(size.width, size.height)
                transform(texture, size)
                val surface = Surface(texture.surfaceTexture)
                @Suppress("DEPRECATION")
                device.createCaptureSession(listOf(surface), object : CameraCaptureSession.StateCallback() {
                    override fun onConfigured(session: CameraCaptureSession) {
                        val request = device.createCaptureRequest(CameraDevice.TEMPLATE_PREVIEW).apply { addTarget(surface) }
                        try {
                            session.setRepeatingRequest(request.build(), null, main)
                        } catch (e: Exception) {
                            // Caméra fermée entre-temps.
                        }
                    }

                    override fun onConfigureFailed(session: CameraCaptureSession) {}
                }, main)
            }

            override fun onDisconnected(device: CameraDevice) = closePreview()
            override fun onError(device: CameraDevice, error: Int) = closePreview()
        }, main)
    }

    private fun closePreview() {
        camera?.close()
        camera = null
        RecorderService.previewing = false
    }

    /** Écran en paysage : l'image de la caméra est tournée et remplit l'écran. */
    private fun transform(view: TextureView, size: Size) {
        @Suppress("DEPRECATION")
        val rotation = windowManager.defaultDisplay.rotation
        val matrix = Matrix()
        val viewRect = RectF(0f, 0f, view.width.toFloat(), view.height.toFloat())
        if (rotation == Surface.ROTATION_90 || rotation == Surface.ROTATION_270) {
            val bufferRect = RectF(0f, 0f, size.height.toFloat(), size.width.toFloat())
            bufferRect.offset(viewRect.centerX() - bufferRect.centerX(), viewRect.centerY() - bufferRect.centerY())
            matrix.setRectToRect(viewRect, bufferRect, Matrix.ScaleToFit.FILL)
            val scale = maxOf(view.height.toFloat() / size.height, view.width.toFloat() / size.width)
            matrix.postScale(scale, scale, viewRect.centerX(), viewRect.centerY())
            matrix.postRotate(90f * (rotation - 2), viewRect.centerX(), viewRect.centerY())
        }
        view.setTransform(matrix)
    }

    // --- Droits et service ---

    private val permissions = buildList {
        add(Manifest.permission.CAMERA)
        add(Manifest.permission.RECORD_AUDIO)
        if (Build.VERSION.SDK_INT >= 33) add(Manifest.permission.POST_NOTIFICATIONS)
    }

    private fun hasPermissions() =
        permissions.take(2).all { checkSelfPermission(it) == PackageManager.PERMISSION_GRANTED }

    private fun askPermissions() {
        val missing = permissions.filter { checkSelfPermission(it) != PackageManager.PERMISSION_GRANTED }
        if (missing.isNotEmpty()) requestPermissions(missing.toTypedArray(), 1)
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (prefs.token != null) startService()
    }

    private fun startService() {
        if (prefs.token != null && hasPermissions() && !RecorderService.running) RecorderService.start(this)
    }

    /** Samsung et d'autres coupent les applis en veille : on demande à être laissé tranquille. */
    @SuppressLint("BatteryLife")
    private fun askBatteryExemption() {
        if (getSystemService(PowerManager::class.java).isIgnoringBatteryOptimizations(packageName)) return
        try {
            startActivity(Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, Uri.parse("package:$packageName")))
        } catch (e: Exception) {
            // Réglage absent sur ce téléphone.
        }
    }

    // --- Éléments d'écran ---

    private fun text(value: String, size: Float) = TextView(this).apply {
        text = value
        textSize = size
        setPadding(0, dp(8), 0, dp(8))
    }

    private fun column(vararg views: View) = LinearLayout(this).apply {
        orientation = LinearLayout.VERTICAL
        setPadding(dp(24), dp(24), dp(24), dp(24))
        views.forEach { addView(it, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT)) }
    }

    private fun dp(value: Int) =
        TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, value.toFloat(), resources.displayMetrics).toInt()
}
