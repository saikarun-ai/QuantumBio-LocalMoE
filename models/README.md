# Model Directory

Drop quantized model weights in this directory for the Local MoE engine to pick up.

Supported formats (see `QUANTIZATION_TYPE`):

- **GGUF** - e.g. `DeepSeek-R1-Distill-Q4_K_M.gguf`, `Q4_K_M`, `Q5_K_S`, `Q8_0`
- **AWQ** - `INT4` / `AWQ` weight directories for vLLM

Example:

```
models/
├── DeepSeek-R1-Distill-Q4_K_M.gguf
├── llama-3.2-1b-draft.gguf
└── my-awq-model/
```

If no model weights are present the engine runs in offline fallback mode so the
API and pipelines remain fully testable in an air-gapped environment.