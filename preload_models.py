"""Optional: pre-download all default models for a completely offline Windows build."""
from pathlib import Path
from huggingface_hub import snapshot_download, hf_hub_download

root=Path(__file__).resolve().parent/'bundled_models'
for size in ('tiny','base'):
    whisper=root/'whisper'/size
    print('Scarico faster-whisper-'+size+'...')
    snapshot_download(repo_id='Systran/faster-whisper-'+size,local_dir=str(whisper),
                      ignore_patterns=['*.md','*.txt','.gitattributes'])
    if not (whisper/'model.bin').exists():raise RuntimeError('Whisper '+size+' model.bin non trovato!')
print('Scarico Qwen3-0.6B Q4_K_M...')
model=hf_hub_download(repo_id='tensorblock/Qwen_Qwen3-0.6B-GGUF',
     filename='Qwen3-0.6B-Q4_K_M.gguf',local_dir=str(root/'smarttext'))
print('Modelli pronti in',root)
