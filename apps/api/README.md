# @verolas/api

Verolas API gateway. The runtime is Python 3.12 FastAPI plus Pydantic v2 for typed APIs, with Rust used for performance critical paths (geometry kernel, FEA result processing, drawing parsing).

This directory carries a Node package marker only so Turborepo can orchestrate cross language builds. Real scaffolding lands when the backend workstream comes online.
