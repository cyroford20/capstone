"""Convert all .h5 Keras LSTM models in dataset/models/ to TensorFlow SavedModel format.

This helps safer serving/loading in production.
"""
from pathlib import Path
from tensorflow import keras
import tensorflow as tf
import os


ROOT = Path(__file__).resolve().parent
MODELS_DIR = ROOT / 'models'


def convert_all():
    for h5 in MODELS_DIR.glob('*.h5'):
        name = h5.stem
        saved_dir = MODELS_DIR / f'saved_{name}'
        if saved_dir.exists():
            print(f'SavedModel exists for {name}, skipping')
            continue
        try:
            # load with compile=False to avoid issues deserializing custom metrics
            model = keras.models.load_model(h5, compile=False)
            # use tf.saved_model.save to export SavedModel directory
            tf.saved_model.save(model, str(saved_dir))
            print(f'Converted {h5.name} -> {saved_dir}')
        except Exception as e:
            print(f'Failed to convert {h5.name}: {e}')


if __name__ == '__main__':
    convert_all()
