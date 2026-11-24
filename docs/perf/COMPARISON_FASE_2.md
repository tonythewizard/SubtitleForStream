# Replay locale e risultati dello scheduler

Windows, Python 3.12.10, Ryzen 7 7800X3D, RTX 3070 Ti e RX 570. I due WAV mono sono sintetizzati con la voce Windows predefinita usando queste frasi: “This is a live caption test for the first source.” e “The second speaker is testing the subtitle overlay.” Il replay inietta PCM a blocchi di 20 ms in entrambe le sorgenti, attraversa cattura simulata e ASR e interroga `/state` su loopback. Per ripeterlo impostare `HF_HUB_OFFLINE=1` ed eseguire `python -m tools.replay primo.wav secondo.wav --model medium --device cuda:0`.

| Profilo | Sorgenti raggiunte | Finali pubblicati | Scarti per età | Callback → pubblicazione finale |
| --- | ---: | ---: | ---: | --- |
| CPU INT8, medium | 0/2 | 0 | 4 | Nessun finale |
| CUDA FP16, medium | 2/2 | 2 | 0 | 0,765 s e 0,734 s |
| Vulkan RX 570, medium q5_0 | 1/2 | 0 | 3 | Una sola anteprima |
| CPU INT8, tiny | 2/2 | 3 | 0 | 0,703 s per WAV 1 e p95 0,776 s per WAV 2 |

Il test CPU tiny ha letto il modello dalla cache locale di SubtitleForEveryone tramite override in memoria della root per quel processo. Ogni profilo è stato provato una volta. Per CUDA medium, p50/p95/p99 delle anteprime pubblicate sono 0,266/0,307/0,312 s su WAV 1 e 0,469/0,510/0,515 s su WAV 2. Il replay stampa anche le distribuzioni di coda e inferenza e i conteggi per sorgente. I risultati descrivono questi campioni e queste configurazioni. Il callback rappresenta l'ingresso PCM simulato, non il tempo del dispositivo o il rendering OBS.

Il test di regressione della coda falliva sulla politica originale: con un finale microfono e quattro finali Discord accodati a capacità quattro, veniva scartato il microfono. Con la nuova politica resta il finale microfono e viene contato uno scarto Discord. Il test verifica anche precedenza dei finali, sostituzione delle anteprime e alternanza fra sorgenti.

La prova con medium su CPU e RX 570 non raggiunge il criterio operativo delle due sorgenti. Questo blocca la qualificazione di quei profili e richiede prove su segmentazione, carico e modelli più piccoli. Restano da misurare WER/CER, rendering OBS, RAM/VRAM e stabilità in una diretta prolungata.
