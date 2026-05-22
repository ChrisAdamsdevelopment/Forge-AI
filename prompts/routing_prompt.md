# Forge Routing Prompt

Classify the user's request into one or more task routes.

Routes:
- research
- coding
- file_ops
- rag_design
- module_design
- module_execution
- app_architecture
- debugging
- eval_design
- training_design
- security_review

For each route, return:
- route name
- confidence
- required sources
- tools likely needed
- approval risk
- expected output type

Use JSON:

{
  "routes": [
    {
      "name": "module_design",
      "confidence": 0.92,
      "sources": ["docs/tasker_style_module_system.md", "modules/specs/module_architecture.md"],
      "tools": [],
      "approval_risk": "low",
      "output": "module manifest + prompt + schemas"
    }
  ]
}
