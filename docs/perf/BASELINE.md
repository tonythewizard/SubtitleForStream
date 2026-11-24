# Baseline e piano di misura

Base locale: `dc951d0`, Windows, Python 3.12.10, AMD Ryzen 7 7800X3D. I 15 test preesistenti sono passati invocando le funzioni di test nella venv locale. Il replay della fase 1 usa due ID di sorgente, un thread controllato da eventi e caption sintetiche. Backend, modello e file WAV non sono coinvolti.

Sulla base, la GUI arrestava i worker ASR e LLM richiedendo la cancellazione tramite evento, poi permetteva un nuovo avvio anche se il decoder precedente era ancora attivo. Il tempo indicato come ritardo partiva dall'accodamento del clip. L'overlay richiedeva lo stato ogni 50 ms, anche in assenza di modifiche.

Per la misura end-to-end servono timestamp correlati con ID di sessione, sorgente, frase e revisione. Registrare la fine del parlato di riferimento, accodamento, inizio e fine inferenza, pubblicazione e rendering. Per OBS usare un riferimento temporale comune o un protocollo di calibrazione documentato. Tenere separati anteprime e finali e contare clip scartati e finali mancanti. Distribuzioni p50/p95/p99, WER/CER, CPU, RAM e VRAM restano da rilevare sullo stesso corpus autorizzato, modello e hardware. Il replay sintetico verifica soltanto il comportamento del lifecycle.
