if __name__ == "__main__":
    # download test data
    import pandas as pd

    df = pd.read_parquet(
        "hf://datasets/Aoschu/German_invoices_dataset/data/train-00000-of-00001-f9d614282a2aa4e0.parquet")
