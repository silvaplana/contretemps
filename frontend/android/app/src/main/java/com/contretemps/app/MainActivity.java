package com.contretemps.app;

import android.content.Intent;
import android.net.Uri;
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
        partage(getIntent());
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        partage(intent);
    }

    /**
     * « Partager » d'Android vers l'appli (Seb, 13/11) : ouvre la même page que
     * le share_target de la PWA, `/partage?title=…&text=…`, qui montre « Envoyer à… »
     * (frontend/src/utils/envoyerA.js).
     */
    private void partage(Intent intent) {
        if (intent == null || !Intent.ACTION_SEND.equals(intent.getAction())) return;
        String texte = intent.getStringExtra(Intent.EXTRA_TEXT);
        String serveur = getBridge() != null ? getBridge().getServerUrl() : null;
        if (texte == null || serveur == null) return;
        Uri.Builder adresse = Uri.parse(serveur).buildUpon().path("/partage").clearQuery();
        String titre = intent.getStringExtra(Intent.EXTRA_SUBJECT);
        if (titre != null) adresse.appendQueryParameter("title", titre);
        adresse.appendQueryParameter("text", texte);
        String url = adresse.build().toString();
        setIntent(new Intent()); // pas rejoué en tournant l'écran
        getBridge().getWebView().post(() -> getBridge().getWebView().loadUrl(url));
    }
}
