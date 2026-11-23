// Les dessins des boutons du Timer (Seb, 21/11, maquette
// https://claude.ai/artifact/3L9dnVxxWC1UKoNioRpX9V) : le chronomètre de
// l'arbitre pour Pause / Reprendre, la cloche du ring vue de face pour Arrêter
// (le marteau tape trois coups, animation dans sparring.css).
export const CHRONO = `<svg viewBox="0 0 200 200" aria-hidden="true"><defs>
  <linearGradient id="pcs" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#f4f6f9"/><stop offset=".45" stop-color="#9aa0ab"/><stop offset="1" stop-color="#4a4f59"/></linearGradient>
  <radialGradient id="pdl" cx="40%" cy="32%" r="80%"><stop offset="0" stop-color="#fffdf4"/><stop offset="1" stop-color="#d9d3bf"/></radialGradient>
  <filter id="pf"><feGaussianBlur stdDeviation="4"/></filter></defs>
      <ellipse cx="104" cy="186" rx="60" ry="8" fill="#000" opacity=".5" filter="url(#pf)"/>
      <circle cx="100" cy="20" r="11" fill="none" stroke="url(#pcs)" stroke-width="5"/>
      <rect x="89" y="24" width="22" height="20" rx="4" fill="url(#pcs)" stroke="#3b3f47" stroke-width="1"/>
      <rect x="140" y="38" width="16" height="14" rx="3" fill="url(#pcs)" stroke="#3b3f47" stroke-width="1" transform="rotate(40 148 45)"/>
      <circle cx="100" cy="112" r="74" fill="url(#pcs)" stroke="#2a2d33" stroke-width="1.5"/>
      <circle cx="100" cy="112" r="64" fill="#2a2d33"/>
      <circle cx="100" cy="112" r="61" fill="url(#pdl)"/>
      <g stroke="#3b3f47" stroke-linecap="round"><line x1="100" y1="56" x2="100" y2="66" stroke-width="3.5" transform="rotate(0 100 112)"/><line x1="100" y1="58" x2="100" y2="63" stroke-width="2" transform="rotate(30 100 112)"/><line x1="100" y1="58" x2="100" y2="63" stroke-width="2" transform="rotate(60 100 112)"/><line x1="100" y1="56" x2="100" y2="66" stroke-width="3.5" transform="rotate(90 100 112)"/><line x1="100" y1="58" x2="100" y2="63" stroke-width="2" transform="rotate(120 100 112)"/><line x1="100" y1="58" x2="100" y2="63" stroke-width="2" transform="rotate(150 100 112)"/><line x1="100" y1="56" x2="100" y2="66" stroke-width="3.5" transform="rotate(180 100 112)"/><line x1="100" y1="58" x2="100" y2="63" stroke-width="2" transform="rotate(210 100 112)"/><line x1="100" y1="58" x2="100" y2="63" stroke-width="2" transform="rotate(240 100 112)"/><line x1="100" y1="56" x2="100" y2="66" stroke-width="3.5" transform="rotate(270 100 112)"/><line x1="100" y1="58" x2="100" y2="63" stroke-width="2" transform="rotate(300 100 112)"/><line x1="100" y1="58" x2="100" y2="63" stroke-width="2" transform="rotate(330 100 112)"/></g>
      <g class="sc-timer__pause-signe" fill="#1c1e23"><rect x="74" y="74" width="20" height="76" rx="8"/><rect x="106" y="74" width="20" height="76" rx="8"/></g>
      <path class="sc-timer__lecture-signe" d="M82 80 L138 112 L82 144 Z" fill="#1c1e23" stroke="#1c1e23" stroke-width="7" stroke-linejoin="round"/>
      <path d="M52 92 a54 54 0 0 1 60 -32" fill="none" stroke="#fff" stroke-opacity=".7" stroke-width="7" stroke-linecap="round" filter="url(#pf)"/></svg>`

export const CLOCHE = `<svg viewBox="0 0 200 200" aria-hidden="true"><defs>
      <radialGradient id="lt" cx="36%" cy="30%" r="78%"><stop offset="0" stop-color="#fff6cf"/><stop offset=".22" stop-color="#f6d267"/><stop offset=".6" stop-color="#cf9a2e"/><stop offset="1" stop-color="#6e4a10"/></radialGradient>
      <linearGradient id="rim" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ffe9a0"/><stop offset=".5" stop-color="#a87720"/><stop offset="1" stop-color="#5a3c0c"/></linearGradient>
      <linearGradient id="pl" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#3a3e47"/><stop offset="1" stop-color="#1c1e23"/></linearGradient>
      <radialGradient id="ac" cx="35%" cy="30%" r="75%"><stop offset="0" stop-color="#ffffff"/><stop offset=".5" stop-color="#b9bec8"/><stop offset="1" stop-color="#565b66"/></radialGradient>
      <linearGradient id="tg" x1="0" x2="1"><stop offset="0" stop-color="#8d929c"/><stop offset=".5" stop-color="#e6e9ee"/><stop offset="1" stop-color="#6b707a"/></linearGradient>
      <filter id="fc"><feGaussianBlur stdDeviation="6"/></filter><filter id="fh"><feGaussianBlur stdDeviation="3.5"/></filter></defs>
      <rect x="14" y="14" width="172" height="176" rx="22" fill="url(#pl)" stroke="#4a4f59" stroke-width="1.5"/>
      <g fill="url(#ac)"><circle cx="32" cy="32" r="4.5"/><circle cx="168" cy="32" r="4.5"/><circle cx="32" cy="172" r="4.5"/></g>
      <g fill="none" stroke="#f6d267" stroke-width="4" stroke-linecap="round">
        <path class="sc-timer__onde" d="M22 78 q-12 22 0 44"/><path class="sc-timer__onde sc-timer__onde--2" d="M8 66 q-18 34 0 68"/></g>
      <g class="sc-timer__dome">
        <ellipse cx="103" cy="112" rx="66" ry="64" fill="#000" opacity=".55" filter="url(#fc)"/>
        <circle cx="100" cy="100" r="66" fill="url(#rim)"/>
        <circle cx="100" cy="100" r="61" fill="url(#lt)"/>
        <circle cx="100" cy="100" r="43" fill="none" stroke="#5a3c0c" stroke-opacity=".35" stroke-width="2"/>
        <circle cx="100" cy="100" r="41" fill="none" stroke="#fff3c0" stroke-opacity=".35" stroke-width="1.2"/>
        <circle cx="100" cy="100" r="22" fill="none" stroke="#5a3c0c" stroke-opacity=".3" stroke-width="1.5"/>
        <ellipse cx="78" cy="72" rx="24" ry="13" transform="rotate(-35 78 72)" fill="#fff" opacity=".55" filter="url(#fh)"/>
        <path d="M134 136 a48 48 0 0 1 -50 12" fill="none" stroke="#ffe9a0" stroke-opacity=".35" stroke-width="3" stroke-linecap="round" filter="url(#fh)"/>
        <circle cx="100" cy="100" r="10" fill="#4a3208"/><circle cx="100" cy="100" r="8" fill="url(#ac)"/>
        <path d="M95.5 100 h9 M100 95.5 v9" stroke="#3b3f47" stroke-width="1.6" stroke-linecap="round"/>
      </g>
      <g class="sc-timer__marteau">
        <rect x="174.5" y="108" width="7" height="78" rx="3.5" fill="url(#tg)"/>
        <circle cx="178" cy="100" r="13" fill="#000" opacity=".4" filter="url(#fh)" transform="translate(2 4)"/>
        <circle cx="178" cy="100" r="12" fill="url(#ac)"/>
        <ellipse cx="174" cy="95.5" rx="4" ry="2.6" fill="#fff" opacity=".8"/>
      </g>
      <circle cx="178" cy="186" r="8" fill="url(#ac)" stroke="#2a2d33" stroke-width="1.5"/><circle cx="178" cy="186" r="2.5" fill="#2a2d33"/></svg>`

// Le poing levé du vainqueur (Timer étendu ; Seb, 21/11) : gris tant que
// personne n'est déclaré, en couleur une fois touché.
export const POING = `<svg viewBox="0 10 100 120" aria-hidden="true">
  <defs>
    <linearGradient id="pg-peau" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#f6cfa8"/><stop offset=".55" stop-color="#dba272"/><stop offset="1" stop-color="#a86a40"/></linearGradient>
    <linearGradient id="pg-doigt" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f9d9b6"/><stop offset=".6" stop-color="#e0aa7a"/><stop offset="1" stop-color="#b77a4c"/></linearGradient>
    <linearGradient id="pg-bande" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#8f1009"/><stop offset=".4" stop-color="#e8362a"/><stop offset="1" stop-color="#7a0c06"/></linearGradient>
  </defs>
  <path d="M33 128 31 94h40l-3 34Z" fill="url(#pg-bande)" stroke="#4d0604" stroke-width="1.5" stroke-linejoin="round"/>
  <path d="M32 104c13 4 26 4 38 0M32.5 114c12 4 25 4 36.5 0" fill="none" stroke="rgba(0,0,0,.3)" stroke-width="1.6"/>
  <path d="M20 52c0-8 6-12 14-12h34c9 0 15 6 15 15v22c0 13-9 22-22 22H41c-12 0-21-9-21-21Z" fill="url(#pg-peau)" stroke="#6b3d22" stroke-width="1.5"/>
  <g fill="url(#pg-doigt)" stroke="#6b3d22" stroke-width="1.5">
    <rect x="20" y="32" width="16.5" height="30" rx="8"/>
    <rect x="35.5" y="27" width="16.5" height="35" rx="8"/>
    <rect x="51" y="28" width="16.5" height="34" rx="8"/>
    <rect x="66.5" y="33" width="16" height="29" rx="8"/>
  </g>
  <path d="M24 47h9M39.5 44h9M55 45h9M70.5 48h8.5" fill="none" stroke="#6b3d22" stroke-width="1.3" stroke-linecap="round" opacity=".55"/>
  <path d="M25 37c1.5-2 4-2.5 6-1.5M40.5 32c1.5-2 4.5-2.5 6.5-1.5M56 33c1.5-2 4.5-2.5 6.5-1.5M71 38c1.5-2 4-2.5 6-1.5" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" opacity=".55"/>
  <path d="M14 70c-3-8 2-15 10-15l30-2c8-.5 13 4 13 10s-5 10-12 10.5L30 76c-4 6-13 3-16-6Z" fill="url(#pg-doigt)" stroke="#6b3d22" stroke-width="1.5" stroke-linejoin="round"/>
  <path d="M55 56.5c5 .5 8 3 8 6.5s-3 6-7 6.5" fill="#fbe6d0" stroke="#6b3d22" stroke-width="1" opacity=".8"/>
  <path d="M22 60c6-2 14-2.5 22-3" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" opacity=".45"/>
</svg>`

// Le retardateur du Timer étendu : un petit appareil photo.
export const CAMERA = `<svg viewBox="0 0 64 48" aria-hidden="true"><defs><linearGradient id="cam-c" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#7b818e"/><stop offset=".5" stop-color="#3d414b"/><stop offset="1" stop-color="#1e2026"/></linearGradient><radialGradient id="cam-o" cx=".35" cy=".3" r=".8"><stop offset="0" stop-color="#9fd0ff"/><stop offset=".45" stop-color="#22508f"/><stop offset="1" stop-color="#060b18"/></radialGradient></defs><path d="M22 6h20l4 6h10a5 5 0 0 1 5 5v22a5 5 0 0 1-5 5H8a5 5 0 0 1-5-5V17a5 5 0 0 1 5-5h10z" fill="url(#cam-c)" stroke="#0c0d10" stroke-width="1.5"/><path d="M6 17a3 3 0 0 1 3-3h46a3 3 0 0 1 3 3" fill="none" stroke="rgba(255,255,255,.35)" stroke-width="1.2"/><circle cx="32" cy="27" r="13" fill="#15171c" stroke="#9aa0ad" stroke-width="1.5"/><circle cx="32" cy="27" r="9.5" fill="url(#cam-o)"/><ellipse cx="28.5" cy="23" rx="3" ry="2" fill="#fff" opacity=".7"/><circle cx="52" cy="19" r="2.2" fill="#ff2d20"/></svg>`

// La lampe de la caméra du Timer (maquette du 23/11).
export const LAMPE = `<svg viewBox="0 0 48 48" aria-hidden="true"><g transform="rotate(-35 24 24)"><path d="M18 6h12v6l-3 5H21l-3-5z" fill="#e8eaee" stroke="#2a2d33" stroke-width="1.6" stroke-linejoin="round"/><rect x="20.5" y="17" width="7" height="24" rx="2.5" fill="#7d838e" stroke="#2a2d33" stroke-width="1.6"/><rect x="22.5" y="23" width="3" height="6" rx="1.2" fill="#2a2d33"/><path d="M19.5 7.5h9" stroke="#fffbd2" stroke-width="2.6" stroke-linecap="round"/></g><g stroke="#fff3a0" stroke-width="2.4" stroke-linecap="round"><path d="M33 6l3-4M38 11l5-2M28 3l0-2"/></g></svg>`
