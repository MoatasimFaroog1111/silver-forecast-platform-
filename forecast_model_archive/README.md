# Research model archive

The deployable `main` branch intentionally carries only the six active persisted CatBoost forecast models used by the runtime.

The 54-candidate Stage-9 research archive is retained outside the production Git tree because it is not loaded by the application and adds about 25 MB to every clone and deployment. The complete archive remains available in the project delivery artifacts for audit and research.
