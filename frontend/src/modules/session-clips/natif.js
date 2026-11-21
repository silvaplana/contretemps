import { Capacitor, registerPlugin } from '@capacitor/core'

// Le pont vers l'appli Android « Tournage <école> » (frontend/android,
// camera/TournagePlugin.kt) : le film en tâche de fond, et l'écran en paysage
// pour le Timer étendu.
export const Natif = registerPlugin('Tournage')
export const DANS_L_APPLI = Capacitor.isNativePlatform()
