"""
Training script for the ML Scam-Intent Classifier.

Fits a TF-IDF + Calibrated Logistic Regression pipeline across 5 fraud/conversational categories:
1. credential_theft
2. urgent_financial_coercion
3. remote_access_takeover
4. authority_impersonation
5. benign (including hard negatives)

Outputs:
- models/scam-intent-v1/model.joblib
- models/scam-intent-v1/metadata.json
"""

import json
from pathlib import Path
import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.metrics import classification_report, f1_score, accuracy_score

TRAINING_DATA = [
    # --- 1. Credential Theft ---
    ("Please tell me your OTP to verify your identity.", "credential_theft"),
    ("Read out the six digit verification code sent to your mobile phone.", "credential_theft"),
    ("What is your online banking password and ATM PIN?", "credential_theft"),
    ("Share the one time passcode right now so we can unlock your debit card.", "credential_theft"),
    ("We sent an authentication code to your email. Give it to me immediately.", "credential_theft"),
    ("I need your credit card CVV number and expiration date to verify the charge.", "credential_theft"),
    ("To secure your account, confirm the OTP you just received from your bank.", "credential_theft"),
    ("Do not hang up; read me the two-factor authentication token on your screen.", "credential_theft"),
    ("Give me your login credentials so our system can restore access.", "credential_theft"),
    ("Please verify the security code displayed on your banking app.", "credential_theft"),
    ("Send me your secret pin number to authorize the pending refund.", "credential_theft"),
    ("What is the temporary verification passcode that arrived via SMS?", "credential_theft"),

    # --- 2. Urgent Financial Coercion ---
    ("Transfer money to this safe account immediately to protect your funds.", "urgent_financial_coercion"),
    ("We require an emergency wire transfer immediately to complete the escrow agreement.", "urgent_financial_coercion"),
    ("Your funds are compromised; move all balance to the government safe deposit account.", "urgent_financial_coercion"),
    ("Pay the pending fine right now via crypto or gift cards to avoid arrest.", "urgent_financial_coercion"),
    ("Send the payment within thirty minutes or your account will be permanently frozen.", "urgent_financial_coercion"),
    ("You must purchase five Apple gift cards and read the redemption codes to me.", "urgent_financial_coercion"),
    ("Immediately wire five thousand dollars to the authorized reserve bank account.", "urgent_financial_coercion"),
    ("Act now; make this urgent payment to clear your name before business close.", "urgent_financial_coercion"),
    ("Transfer your savings to this secure holding account right away.", "urgent_financial_coercion"),
    ("Immediate wire transfer is mandatory to prevent foreclosure.", "urgent_financial_coercion"),
    ("Buy Bitcoin at the nearest ATM and deposit it to this government QR wallet.", "urgent_financial_coercion"),
    ("Send the money before police arrive at your residence.", "urgent_financial_coercion"),

    # --- 3. Remote Access Takeover ---
    ("Please install AnyDesk and give me remote access to your computer.", "remote_access_takeover"),
    ("Download TeamViewer so I can clean the critical Trojan virus from your PC.", "remote_access_takeover"),
    ("Open your browser and search for QuickAssist so I can take control of your machine.", "remote_access_takeover"),
    ("Enable screen sharing and allow our remote technician full control of your desktop.", "remote_access_takeover"),
    ("Go to ultraviewer dot net, install the client, and provide the partner ID.", "remote_access_takeover"),
    ("We need remote access to your laptop to scan for bank phishing malware.", "remote_access_takeover"),
    ("Download the support utility from this link so we can fix your server.", "remote_access_takeover"),
    ("Grant remote desktop permissions to our security department immediately.", "remote_access_takeover"),
    ("Install this remote administration tool to verify your internet gateway.", "remote_access_takeover"),
    ("Allow remote access connection so we can cancel the unauthorized debit.", "remote_access_takeover"),

    # --- 4. Authority Impersonation ---
    ("This is Officer Miller from the Federal Police regarding an arrest warrant.", "authority_impersonation"),
    ("I am calling from the Central Tax Authority; you are accused of money laundering.", "authority_impersonation"),
    ("This is Customs and Border Protection; illegal narcotics were seized in your parcel.", "authority_impersonation"),
    ("You are speaking with the cyber crime division of the national police.", "authority_impersonation"),
    ("A federal warrant has been issued in your name for tax fraud and evading court.", "authority_impersonation"),
    ("This is executive headquarters calling regarding an urgent confidential board matter.", "authority_impersonation"),
    ("I am the chief inspector; your bank accounts are under statutory seizure.", "authority_impersonation"),
    ("Calling from the Supreme Court judicial registry; failure to comply leads to arrest.", "authority_impersonation"),
    ("This is state tax enforcement; law enforcement officers are en route to your home.", "authority_impersonation"),
    ("I am senior detective Sharma; answer all questions truthfully under penalty of perjury.", "authority_impersonation"),

    # --- 5. Benign Conversational & Hard Negatives ---
    ("Hello, are we still meeting tomorrow for the project review?", "benign"),
    ("I can meet you at the cafe at ten to review the presentation slides.", "benign"),
    ("Great, see you then; have a wonderful afternoon.", "benign"),
    ("Did you get a chance to look over the pull request I submitted this morning?", "benign"),
    ("I reset my bank password yesterday on my phone and it works smoothly now.", "benign"),  # Hard negative
    ("Never share your OTP or password with anyone calling on the phone.", "benign"),  # Hard negative (educational)
    ("The transfer from my checking to savings account went through without issues.", "benign"),  # Hard negative
    ("Let me know when the meeting starts so I can join the Google Meet room.", "benign"),
    ("Can you send me the PDF file when you finish writing the summary?", "benign"),
    ("I bought some groceries at the supermarket and paid with my credit card.", "benign"),
    ("Our team completed the sprint goals ahead of schedule this week.", "benign"),
    ("Please remember to bring your laptop and charger to the workshop.", "benign"),
    ("What time does the train arrive at the central railway station?", "benign"),
    ("The weather forecast says it will rain tomorrow morning so take an umbrella.", "benign"),
    ("I need to update my contact information on the university student portal.", "benign"),
    ("Thanks for helping me fix that bug in the database query earlier today.", "benign"),
]


def train_and_export():
    texts, labels = zip(*TRAINING_DATA)

    # Use TF-IDF with unigrams + bigrams and sublinear TF
    pipeline = Pipeline([
        (
            "tfidf",
            TfidfVectorizer(
                ngram_range=(1, 2),
                lowercase=True,
                sublinear_tf=True,
                max_features=500,
            ),
        ),
        (
            "clf",
            LogisticRegression(
                C=2.0,
                max_iter=1000,
                class_weight="balanced",
                random_state=42,
            ),
        ),
    ])

    # 5-fold Stratified Cross Validation
    skf = StratifiedKFold(n_splits=4, shuffle=True, random_state=42)
    scores = cross_val_score(pipeline, texts, labels, cv=skf, scoring="f1_macro")
    mean_cv_f1 = float(np.mean(scores))

    # Fit final model
    pipeline.fit(texts, labels)

    # Destination directory
    out_dir = Path("models/scam-intent-v1")
    out_dir.mkdir(parents=True, exist_ok=True)

    model_path = out_dir / "model.joblib"
    joblib.dump(pipeline, model_path)

    metadata = {
        "model_version": "scam-intent-v1",
        "algorithm": "TfidfVectorizer + LogisticRegression",
        "classes": sorted(list(set(labels))),
        "num_training_samples": len(texts),
        "cv_folds": 4,
        "cv_macro_f1": round(mean_cv_f1, 4),
        "feature_version": "tfidf_word_ngram_1_2",
    }

    metadata_path = out_dir / "metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print(f"Model saved to {model_path}")
    print(f"Metadata saved to {metadata_path}")
    print(f"Cross-Validation Macro F1: {mean_cv_f1:.4f}")
    return pipeline, metadata


if __name__ == "__main__":
    train_and_export()
