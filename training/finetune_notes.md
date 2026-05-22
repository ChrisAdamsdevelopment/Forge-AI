# Fine-Tuning Notes

## Default ladder

1. Improve system prompt.
2. Improve project docs.
3. Improve RAG chunking/retrieval.
4. Add examples.
5. Add golden eval tasks.
6. Only then consider LoRA/QLoRA.

## Training data rule

Only train on examples that represent behavior you want repeated.

Bad training data makes the model worse.

## Good examples

A good training row should include:

- clear user request
- correct assistant response
- expected structure
- no fake tool results
- no private secrets
- no unresolved placeholders

## Data sources

Candidate sources for training:

- highly rated Forge conversations
- manually written examples
- successful module runs
- corrected failed responses
- golden task expected outputs

## Validation

Before training:

- remove secrets
- normalize formatting
- ensure role labels are correct
- ensure target model chat template compatibility
- split train/valid
