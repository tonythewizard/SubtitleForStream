# SubtitleForStream v0.2 — patch latenza e allucinazioni

## Cosa cambia

- **VAD Silero integrato in faster-whisper**, attivo per impostazione predefinita. Evita di decodificare molte pause, rumori e porzioni senza voce.
- **Filtro crediti Whisper** che rimuove «Sottotitoli creati dalla comunità Amara.org», varianti «amra.org», «Subtitles by Amara.org», «Sottotitoli a cura di QTSS» e relativo testo spurio. Non cancella frasi normali che parlano del sito Amara.org.
- **Modalità rapida**: aspetta circa 280 ms di silenzio (prima 520 ms) e limita il blocco a circa 2,4 s (prima 3,8 s). Vantaggio: meno attesa; compromesso: maggior rischio di dividere parole/frasi.
- **Modello Whisper tiny** come predefinito nelle nuove installazioni; le impostazioni esistenti sono conservate, inclusa la scelta precedente `base`.
- **Caricamento immediato del modello** al pulsante AVVIA: riduce il blocco iniziale sulla prima frase, dopo che il modello è caricato.
- **Coda limitata a 6 clip**; se è piena scarta il più vecchio. Clip arretrate da più di 4 secondi non sono mostrate su OBS. Non promette di trascrivere tutte le parole su CPU troppo lenta.
- **Misurazione del ritardo** nel log: `Whisper X.XXs · ritardo Y.YYs` per ogni frase pubblicata.
- **Backend opzionale NVIDIA CUDA FP16**; richiede l'ambiente CTranslate2/CUDA/cuDNN su Windows configurato correttamente. Se l'inizializzazione GPU fallisce, ripiega su CPU. Non tocca la RX 570, che non è CUDA.
- **Qwen secondario** usa solo 2 thread CPU e salta le revisioni quando la coda Whisper è occupata.

## Aggiornamento Windows dalla v0.1

1. Chiudi la vecchia SubtitleForStream e fai una copia della vecchia cartella del programma.
2. Estrai questo ZIP in `C:\SubtitleForStream` o in un'altra cartella. Se hai creato `dist\SubtitleForStream` con PyInstaller, non basta sostituire un singolo file `.py`: devi **ricompilare la build**.
3. Da PowerShell nella nuova cartella esegui `powershell -ExecutionPolicy Bypass -File .\setup_windows.ps1`, poi `run_windows.bat` (oppure `build_windows.ps1` per creare l'EXE).
4. Apri **Trascrizione** e seleziona `tiny`, `CPU INT8`, **Modalità rapida**, **VAD** e **Filtro allucinazioni**. Per la v0.1 in cui era stato scelto `base`, l'aggiornamento mantiene `base` fino a quando non scegli `tiny`.
5. Lascia temporaneamente **Qwen disattivato** durante i test di prestazione. Censura, correzione semplice e animazioni CSS funzionano comunque.
6. Premi **AVVIA TRASCRIZIONE**: aspetta il messaggio **Whisper pronto**, poi testa microfono e Discord. La scena e la URL OBS restano uguali (`http://127.0.0.1:8765/overlay` salvo personalizzazioni).
7. In **OBS / Log**, controlla `Whisper 0.XXs · ritardo 0.XXs`. Se il ritardo resta sopra 2–3 secondi anche con `tiny`, la CPU non sta reggendo o l'acquisizione presenta un collo di bottiglia; valuta NVIDIA CUDA o una build GPU diversa.

## Limiti tecnici

- La correzione evita varianti **note** delle allucinazioni di Whisper: non può impedire tutte le frasi inventate. Anche con VAD occasionalmente possono esserci errori.
- La modalità rapida abbassa l'attesa imposta dalla cattura ma non garantisce 200–300 ms di latenza complessiva. Per una vera trascrizione incrementale parola per parola occorre sostituire l'architettura a blocchi con un motore streaming.
- La selezione CUDA non è collaudata su Windows in questo ambiente di generazione. In particolare, non installa automaticamente i DLL NVIDIA richiesti e può ripiegare su CPU.
- Il filtro VAD potrebbe scartare interiezioni troppo brevi o voci molto basse. In tal caso prova a ridurre la soglia dB o disattivare VAD per confronto.
- I test Python verificano logica, regex, coda, serializzazione e rendering HTTP. **Non** verificano periferiche Windows, Discord WASAPI o prestazioni reali.
- I modelli non sono presenti nello ZIP sorgente. La `build_windows_full.ps1` scarica Whisper tiny/base e Qwen e li incorpora nella build, se la connessione è disponibile.
