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
