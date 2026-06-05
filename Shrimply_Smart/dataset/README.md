MLflow experiment tracking for Optuna training

This folder contains the generalized Optuna training script `train_optuna.py`.

How MLflow is used

- If `mlflow` is installed, runs will be logged to `dataset/mlruns/` (local file store).
- The script uses Optuna's MLflowCallback to log trial params/metrics and logs the final model and scaler as artifacts.

Quick commands

Run a quick smoke test (no MLflow required):

```bash
python dataset/train_optuna.py --target humidity --n_trials 5
```

Run with MLflow tracking (after installing mlflow into your venv):

```bash
# from repo root
pip install -r backend/requirements.txt
python dataset/train_optuna.py --target humidity --n_trials 20
# view runs
mlflow ui --backend-store-uri dataset/mlruns --port 5001
```

Notes

- The MLflow UI will read the `dataset/mlruns` directory created by the script.
- If MLflow is not installed the script will still run but prints a notice that tracking is disabled.
