# Audio continuo, backend e overlay

Test locali: 26 funzioni passate. Il resampling a blocchi irregolari riproduce il risultato SciPy sull'intero segnale a 44,1 e 48 kHz, con tolleranza assoluta di 2e-6. Il filtro trattiene il breve contesto richiesto ai bordi dei blocchi. Il percorso a 16 kHz mantiene i campioni originali.

Il replay con gli stessi due WAV sintetici e Whisper medium ha pubblicato tre finali su RTX 3070 Ti. CPU e RX 570 hanno perso tre finali ciascuna per età. La CPU ha perso anche un'anteprima. Il decoder sospende le anteprime quando l'ultima inferenza supera 500 ms, ma la prima anteprima costosa può ancora occupare il decoder durante l'arrivo dei finali. Queste prove singole non stabiliscono un miglioramento percentuale.

L'overlay mantiene l'API snapshot e invia ETag. Il browser attende variazioni fino a due secondi, con risveglio immediato alla pubblicazione e controllo periodico di TTL e impostazioni. I client senza ETag continuano con richieste ordinarie. I test coprono aggiornamento, scadenza senza nuove caption e rifiuto di Host e Origin estranei al loopback.

Per misurare la Browser Source, usare l'URL locale `http://127.0.0.1:8765/overlay?measure=1` e consultare `http://127.0.0.1:8765/render-metrics`. Il browser conferma dopo due callback di animazione il primo inserimento di ciascuna caption ancora presente. Il server misura da pubblicazione a ricezione della conferma con il proprio clock monotono. Questo limite superiore comprende il trasporto e il ritorno della conferma. Non misura l'uscita video di OBS. Il report mantiene al massimo 2048 campioni in memoria e contiene soltanto sorgente e secondi. È stato testato l'endpoint di conferma. Il collaudo funzionale OBS della build precedente è stato confermato dall'utente.

Per il rollback di questa iterazione, ripristinare insieme overlay HTML, server HTTP e CaptionState alla revisione precedente e ripristinare il resampling per blocco nel modulo audio. Conservare controller e scheduler se si desidera mantenere il lavoro precedente.
