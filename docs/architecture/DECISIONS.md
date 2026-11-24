# Decisioni sul lifecycle

- Il controller viene chiamato dal thread proprietario, mentre i worker pubblicano mediante una vista associata a una generazione. Lo stesso lock protegge la pubblicazione e l'invalidazione effettuata da Stop.
- Stop invalida la generazione e svuota le caption visibili. La sessione successiva attende la terminazione di ASR, revisore e cattura. Il timer osserva la terminazione senza eseguire join nella GUI. Dopo cinque secondi di attesa viene registrata una diagnostica. Una chiamata nativa bloccata indefinitamente richiede ancora un meccanismo di isolamento e recupero.
- Al cambio di sorgente la cattura precedente riceve lo stop prima di riaprire i dispositivi. OBS WebSocket e arresto del server overlay eseguono l'I/O fuori dal thread della finestra. La chiusura effettiva attende il server e i worker gestiti.
- Il log dell'inferenza conserva ID sorgente e tempi, omettendo il testo delle caption. Gli eventi di log accodati da sessioni invalidate vengono ignorati.

I file di codice toccati sono `app/controller.py`, `app/main.py`, `app/audio.py` e `app/engine.py`. I test sono in `tests/test_controller.py`. Per il rollback, ripristinare insieme i file di codice alla base `dc951d0` e rimuovere il controller aggiunto. Il formato di configurazione non richiede migrazioni.

La coda ASR assegna precedenza ai finali e alterna le sorgenti disponibili preservando l'ordine interno. Quando tutti i posti sono occupati da finali, sacrifica un clip della sorgente con più slot. I contatori registrano la perdita anche se riguarda un finale. I campioni numerici sono limitati a 2048 valori per sorgente, fase e tipo di clip.

Qwen verifica la disponibilità del decoder e della coda prima della revisione e durante la generazione a token. Gli errori applicano un intervallo crescente fino a 60 secondi. Una risposta malformata lascia visibile Whisper. Il limite di generazione è cooperativo e può essere superato durante il caricamento o un'operazione nativa indivisibile. Le prove di Qwen di questa iterazione usano risposte simulate.

L'overlay usa attese HTTP limitate a otto richieste concorrenti e conserva il binding a loopback. Host e Origin devono appartenere all'endpoint locale. La diagnostica browser è opt-in e rimane in memoria. Le finestre di resampling conservano contesto FIR e fase tra callback. Se whisper.cpp non termina entro il timeout di arresto, il backend forza la terminazione e attende di nuovo il processo.
