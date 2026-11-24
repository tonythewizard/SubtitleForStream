# Confronto fase 1

Il replay trattiene una simulazione d'inferenza mentre vengono richiesti Stop e un nuovo Start. Finché è trattenuta esiste un solo worker. Dopo Stop il tentativo di pubblicare le caption delle due sorgenti lascia lo stato vuoto. Una volta terminato il worker, parte la sessione successiva e pubblica separatamente per entrambe le sorgenti. Una revisione della generazione precedente viene rifiutata anche se usa l'ID di una caption corrente.

Eseguire dalla root con la venv attiva: `python -m pytest -q`. Se pytest non è installato, il replay si esegue con `python -c "from tests.test_controller import test_stop_start_waits_for_inference_and_discards_old_caption as test; test()"`.

Esito locale: 16 test passati tramite invocazione diretta. Nessuna misura di latenza della GPU, della cattura reale o del rendering OBS è stata raccolta.
