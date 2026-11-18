# SubtitleForStream · Roadmap GitHub

**Obiettivo della prima release pubblica:** un unico installer per Windows 11 x64, scaricabile da GitHub Releases. Installa SubtitleForStream come applicazione Windows, crea una scorciatoia sul Desktop e una nel menu Start e consente di avviare i sottotitoli locali in OBS. Lo stesso installer serve PC con CPU, NVIDIA CUDA o AMD Vulkan. Whisper è il percorso principale e Qwen rimane opzionale.

Le versioni sotto sono milestone proposte. Ogni milestone si chiude al raggiungimento dei criteri indicati.

Il [progetto di compatibilità Windows](COMPATIBILITY.md) definisce i componenti del setup unico, il ripiego CPU e la matrice di collaudo.

## Punto di partenza

- L'app desktop, l'overlay locale, il selettore del backend e gli script di build esistono.
- Whisper `medium` su RTX 3070 Ti/CUDA è stato verificato in inferenza. La latenza completa da sorgente a OBS va misurata.
- Whisper `medium` Q5 su RX 570/Vulkan è stato verificato in inferenza. Su un campione sintetico da 1 s ha richiesto circa 1,90 s alla seconda prova. Il profilo Vulkan per il live resta da qualificare.
- La suite attuale comprende 15 test. Serve una prova ripetibile su Windows pulito, senza dipendere dal PC di sviluppo.
- Il setup Inno è stato installato e avviato tramite scorciatoia sul PC di sviluppo. La copia installata ha richiesto una correzione locale per caricare CUDA. Il pacchetto universale e i backend su PC puliti restano da qualificare.

## Milestone 0 · Installer e identità Windows

- [ ] Creare un'identità visiva riconoscibile anche a 16 px. Conservare il sorgente del logo e produrre un file ICO multirisoluzione per app, configurazione di installazione, scorciatoie e voce di disinstallazione. Verificare resa su sfondi chiari e scuri e a diversi livelli DPI.
- [ ] Applicare l'icona alla finestra PySide6 e alla barra delle applicazioni, all'eseguibile PyInstaller e all'installer Inno Setup. Allineare nome, versione, descrizione, editore e identificatore dell'app nei rispettivi metadati Windows.
- [ ] Distribuire un solo `SubtitleForStream-Setup-<versione>-x64.exe`. Includere app e runtime Python e Qt. Installare per utente, con collegamento Desktop selezionato di default e collegamento nel menu Start. Verificare la voce in **Impostazioni → App installate** e la rimozione delle scorciatoie alla disinstallazione.
- [ ] Integrare il percorso CPU nel pacchetto base. Al primo avvio rilevare i dispositivi compatibili e proporre un backend con scelta manuale e indicazione del backend effettivo. Installare o scaricare i componenti CUDA/Vulkan compatibili secondo le condizioni di redistribuzione e verificare gli hash prima dell'uso. Sul PC dell'utente finale Vulkan deve richiedere un driver compatibile, non SDK o compilatori. Il setup deve funzionare anche su PC con la sola CPU.
- [ ] Guidare il primo avvio dalla scelta della sorgente al test del sottotitolo e al collegamento OBS. Mostrare stato, avanzamento e possibilità di riprendere il download dei modelli. Separare dati utente e file dell'app per preservare preferenze e modelli durante gli aggiornamenti.
- [ ] Unificare le versioni di PyInstaller, Inno Setup e GitHub Releases. Definire flusso di aggiornamento, comportamento se l'app è aperta e strategia di firma di eseguibile e installer prima del rilascio pubblico.

**Criterio di uscita:** da una macchina Windows pulita, un utente lancia il setup, trova l'app nel menu Start e sul Desktop, la avvia e visualizza i primi sottotitoli. La stessa build viene provata su CPU, NVIDIA e AMD con una matrice di compatibilità esplicita. Aggiornamento e disinstallazione vengono verificati prima di pubblicare.

## Milestone 1 · Repository pronto per la pubblicazione

- [ ] Inizializzare Git e aggiungere un `.gitignore` **prima** del primo commit. Escludere `.venv`, cache Python, modelli e download, SDK, `whisper-vulkan-build`, `vk-build`, binari, installer generati, configurazioni utente e screenshot diagnostici. Conservare gli script che riproducono la build.
- [ ] Verificare il contenuto in staging e l'eventuale storico per credenziali, percorsi personali, dati audio, log e file di grandi dimensioni. Per le immagini pubbliche usare acquisizioni dimostrative apposite.
- [ ] Scegliere una licenza per il codice, verificare separatamente i termini di modelli e dipendenze, includere gli avvisi applicabili. Documentare quali componenti possono essere ridistribuiti negli artefatti.
- [ ] Aggiornare il README con una descrizione breve, screenshot o demo OBS, installazione rapida, matrice dei backend e limiti. Aggiungere `CONTRIBUTING.md`, `CHANGELOG.md`, istruzioni per segnalare bug e un canale per problemi di sicurezza.

**Criterio di uscita:** un checkout pulito contiene tutto il necessario per iniziare e la documentazione spiega cosa scaricare e dove. Staging e licenze sono stati revisionati prima di qualsiasi push pubblico.

## Milestone 2 · Beta tecnica

- [ ] Rendere ripetibili setup e build su Windows 11 x64. Definire la versione Python e fissare le dipendenze usate per i rilasci. Verificare il setup CPU su una macchina senza CUDA o Vulkan SDK.
- [ ] Rendere espliciti il backend selezionato, quello effettivamente attivo, lo stato del download e il motivo di eventuali ripieghi. Verificare persistenza della selezione, arresto, riavvio e chiusura del processo Vulkan.
- [ ] Separare gli strumenti di sviluppo Vulkan dai requisiti dell'utente finale. Confezionare il runtime Vulkan in un artefatto verificabile se le condizioni di redistribuzione lo consentono. Mantenere la build da sorgente documentata.
- [ ] Costruire una prova ripetibile su audio italiano con testo di riferimento, voce rapida, rumore e più sorgenti. Usare audio sintetico o campioni autorizzati. Per ogni backend riportare modello, quantizzazione, hardware, avvio a freddo, p50/p95 del primo sottotitolo e del testo stabile, parole errate o omesse, scarti di coda e uso di VRAM.
- [ ] Confrontare CUDA `medium` con `large-v3-turbo` e Vulkan Q5 `base`/`small`/`medium`. Misurare anche con OBS attivo. Scegliere un profilo consigliato per backend in base ai risultati.
- [ ] Aggiungere CI Windows per test e build. Coprire finestre sovrapposte, priorità del testo finale, migrazione impostazioni e sicurezza dei dati mostrati nell'overlay. Eseguire i test accelerati su hardware reale.

**Criterio di uscita:** setup pulito e CI verdi. La matrice indica quali combinazioni sono adatte al live. Come obiettivo iniziale, misurare p95 entro 1 s per il primo testo utile e 1,5 s dalla fine della frase per la versione stabile, dichiarando in modo esplicito le configurazioni che raggiungono questi valori.

## Milestone 3 · Release candidata

- [ ] Preparare un pacchetto Windows leggero con download modelli al primo uso. Provare installazione, aggiornamento, disinstallazione e comportamento offline con un modello già disponibile. Pubblicare checksum SHA-256 per gli artefatti candidati.
- [ ] Eseguire una sessione di almeno 60 minuti con microfono, Discord e OBS. Controllare sincronizzazione, recupero dopo disconnessione e stabilità di memoria e processi. Provare anche porta occupata, modello mancante e riavvio di OBS.
- [ ] Controllare che overlay e server di inferenza ascoltino solo in locale. Verificare che password, audio e sottotitoli non finiscano in configurazioni persistenti, log distribuiti o telemetria.
- [ ] Preparare la pagina GitHub Releases con note di versione, guida ai download, requisiti e problemi noti. Usare un tag prerelease e raccogliere riscontri prima del tag stabile.

**Criterio di uscita:** installazione riuscita da una macchina pulita, sessione live completata, guida verificata da una seconda persona e nessun problema aperto che blocchi installazione, avvio, trascrizione o overlay.

## Dopo la prima release

- Valutare Parakeet e altri motori solo tramite confronto ripetibile sullo stesso audio e hardware.
- Migliorare qualità e prestazioni Vulkan sulla base dei profili pubblicati. Estendere la matrice ad altre GPU quando sono disponibili test reali.
- Valutare firma del pacchetto, aggiornamenti e altre piattaforme dopo aver consolidato il rilascio Windows.

**Prossima attività:** qualificare la build CPU su Windows pulito e rendere visibile il backend effettivo. Poi integrare il gestore dei runtime CUDA e Vulkan e collaudarlo con lo stesso installer.
