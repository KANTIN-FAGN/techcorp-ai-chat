import pandas as pd

def delete_lignes(df):

    suspicious = df[df.apply(lambda row: row.astype(str).str.contains(
        "p0up33", case=False, regex=True
    ).any(), axis=1)]

    return df.drop(index=suspicious.index)
