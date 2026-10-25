# Deadlock Detection & Recovery: Resource Allocation Graph Visualizer

> **Operating Systems (BCSE303L) Course Project**  
> **Team Members**:
> - **Sri Krishna** (24BCE2630)
> - **Rithvik Ravi** (24BCE2254)
> - **Aditya** (24BCE2242)

The complete suite is located in the [`deadlock-suite/`](deadlock-suite/) directory.

### Quick Commands:
```bash
cd deadlock-suite
pip install -r requirements.txt
python main.py --scenario safe
python main.py --scenario deadlocked --viva
uvicorn server:app --reload
pytest -v
```

Please see [`deadlock-suite/README.md`](deadlock-suite/README.md) for full architecture, screenshots, benchmarks, and documentation.
