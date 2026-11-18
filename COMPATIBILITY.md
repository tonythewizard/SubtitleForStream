# SubtitleForStream · Progetto di compatibilità Windows

## Impegno per la prima release

Un solo `SubtitleForStream-Setup-<versione>-x64.exe` per **Windows 11 x64**. L’installer include l’app e le dipendenze necessarie a eseguire Whisper su CPU, senza Python, compilatori o SDK preinstallati. CPU è il percorso di base. CUDA e Vulkan sono opzioni accelerate che l’app abilita dopo una prova sul dispositivo effettivo.

Il primo modello si scarica quando serve. Dopo la preparazione del modello, trascrizione e overlay devono funzionare anche senza Internet. Offline al primo avvio l’app spiega che manca il modello e permette di riprovare. Un pacchetto offline con modello incluso può essere valutato in seguito.

**Stato attuale:** abbiamo installato l’app su un PC già configurato. La copia installata ha caricato CUDA solo dopo un intervento locale sulle DLL. Vulkan è stato collaudato sulla RX 570 dai sorgenti, con un server preparato separatamente.

**Prova intermedia del pacchetto 0.2.0.** L’eseguibile originale della build, senza le DLL aggiunte all’installazione, è partito con un profilo dati vuoto e `PATH` limitato alle cartelle Windows. Con CPU selezionata e le sorgenti disattivate, l’overlay ha risposto e Whisper `tiny` è stato scaricato. Alla riapertura con Hub offline, CTranslate2 è stato caricato, l’overlay ha risposto e il modello è rimasto invariato. Il test è stato eseguito sul PC di sviluppo, quindi non certifica le dipendenze di sistema, la cattura del microfono o la trascrizione effettiva nell’installer su Windows pulito.

## Contenuto del pacchetto e accelerazione

| Percorso | Cosa installa l’app | Requisito sul PC | Profilo iniziale da qualificare |
| --- | --- | --- | --- |
| CPU | CTranslate2 e dipendenze native incluse. Modello CTranslate2 gestito dall’app | CPU x64 compatibile con la build effettiva | Whisper `tiny` INT8 |
| NVIDIA CUDA | Modello CTranslate2 condiviso con CPU. Pacchetto CUDA/cuDNN compatibile con la versione di CTranslate2 | GPU e driver NVIDIA che superano la prova di inferenza | `medium` o `large-v3-turbo`, da scegliere con benchmark |
| AMD Vulkan | `whisper-server` compilato e relative DLL. Modello GGML distinto | Driver Vulkan funzionante sulla GPU scelta | Confronto fra `base` e `small` Q5 sulla RX 570 |

I runtime accelerati devono essere **versionati per release, installabili dall’app su richiesta e riutilizzabili offline**. Il setup base rimane unico. Se le condizioni di redistribuzione impediscono di fornire un componente, l’app spiega quale prerequisito ufficiale manca e conserva CPU come percorso disponibile. Qwen rimane facoltativo e non blocca l’avvio di Whisper.

### Struttura dei file

- **Directory di installazione.** Eseguibile e dipendenze immutabili della release. La build non deve utilizzare DLL o modelli che trova per caso su `PATH` o nel workspace di sviluppo.
- **Directory dati per utente.** Impostazioni, cache dei modelli e sottodirectory runtime per backend e versione. La cartella dati precedente resta leggibile per gli utenti che hanno già scaricato modelli.
- **Manifest della release.** Per ogni pacchetto, identificatore backend, versione, compatibilità app/motore, formato modello, URL, dimensione e SHA-256 atteso. Prima della distribuzione, definire come autenticare il manifest e firmare gli eseguibili.
- **Installazione dei componenti.** Scaricare in una cartella temporanea, verificare hash e contenuti ammessi e attivare il pacchetto solo a estrazione riuscita. Tenere utilizzabile l’ultima versione verificata se l’aggiornamento fallisce. Caricare le DLL dal percorso esplicito del runtime. Un errore del driver non deve innescare il download di un modello già integro.

## Scelta del backend e primo avvio

1. All’apertura, controllare in background architettura, driver e componenti locali. Mostrare **Automatico**, **CPU** e le singole GPU rilevate. Distinguere *rilevata*, *componenti mancanti*, *verificata* e *non utilizzabile*. Una GPU elencata non è una garanzia di compatibilità.
2. Preparare il modello di base e renderne visibili i passaggi: ricerca in cache, download, verifica e caricamento. In **Automatico**, usare subito CPU se nessuna accelerazione è già verificata. Proporre l’attivazione GPU senza bloccare la trascrizione di base.
3. Per abilitare CUDA o Vulkan, eseguire in un processo di prova a tempo limitato un’inferenza locale su un campione incorporato o generato. Verificare che l’inferenza abbia davvero usato la GPU selezionata. Per Vulkan, il rilevamento dell’utente finale deve funzionare anche in assenza di `vulkaninfo` e SDK.
4. Se la prova riesce, memorizzare l’esito per **GPU, driver, backend e versione del runtime**. Se fallisce, mostrare il motivo, continuare in CPU e consentire una nuova prova manuale. Ripetere la verifica dopo un cambio di driver, runtime o GPU. Un errore durante una diretta deve poter far ripiegare l’app senza chiudere l’overlay.
5. Mostrare sempre il **backend effettivo**, anche dopo un ripiego. Nel test iniziale guidato, verificare prima l’ingresso audio e poi l’overlay. Esportare, su richiesta, una diagnostica con versioni, dispositivi ed errori tecnici; escludere audio, sottotitoli, password OBS e credenziali.

## Matrice minima di collaudo

| Ambiente | Prova che chiude il caso |
| --- | --- |
| Windows 11 x64 pulito, senza GPU dedicata | Installazione per utente, apertura dal Desktop, acquisizione microfono, primo download, testo atteso in OBS e riavvio offline con cache già pronta |
| PC NVIDIA distinto da quello di sviluppo | Stesso setup, attivazione CUDA dall’app, prova su GPU confermata e sottotitoli live. Simulare componente mancante e verificare il ripiego CPU |
| AMD con RX 570 e una Radeon più recente | Stesso setup, attivazione Vulkan senza SDK, prova GPU confermata, scelta fra modelli Q5 e misura della latenza con OBS aperto |
| PC con più GPU | Selezione manuale dell’adattatore, avvio ripetuto dopo riordino o cambio driver e visualizzazione della GPU effettiva |
| VM o PC con rete assente o instabile | Primo avvio senza modello, download interrotto, ripresa, hash errato, cache integra riutilizzata offline |
| Aggiornamento di una versione installata | Conferma Sì/No, pacchetto verificato, chiusura corretta, riapertura, collegamenti coerenti e conservazione di preferenze e modelli |

Ogni prova registra versione Windows, CPU, GPU, driver, versione app/runtime, modello scelto, backend effettivo e risultato. I test automatici coprono selezione, ripiego, manifest e pacchetti incompleti. Le prove accelerate richiedono hardware reale. La compatibilità si dichiara per le combinazioni provate; la qualifica per il **live** richiede inoltre misure di latenza e qualità con voce reale o campioni autorizzati.

## Ordine di implementazione

1. **Baseline pulita.** Rendere ripetibile la build base e provarla da Windows senza ambiente di sviluppo. Introdurre stato e diagnostica del backend effettivo.
2. **Runtime gestiti.** Separare cache e binari accelerati, introdurre manifest, verifica e installazione atomica. Aggiungere il controllo di inferenza per CPU, CUDA e Vulkan.
3. **Percorso utente.** Integrare il selettore Automatico, l’installazione guidata dei componenti e il ripiego CPU.
4. **Qualifica.** Eseguire la matrice sullo stesso installer e registrare i risultati. Abilitare o raccomandare solo i profili che superano le prove. Pubblicazione e ricompilazione dell’installer restano soggette ad autorizzazione esplicita.
