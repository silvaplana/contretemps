package com.contretemps.app;

import android.os.Bundle;
import com.contretemps.app.camera.TournagePlugin;
import com.getcapacitor.BridgeActivity;

/** L'appli « Tournage <école> » : le site de l'école (server.url) dans Capacitor. */
public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        // Le film de Fights › Tournage (camera/), à enregistrer avant super.onCreate().
        registerPlugin(TournagePlugin.class);
        super.onCreate(savedInstanceState);
        // Propose les nouvelles versions publiées par GitHub Actions (et notifie en arrière-plan).
        Updater.init(this, getString(R.string.ecole));
    }
}
