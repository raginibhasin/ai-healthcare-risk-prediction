import pandas as pd
import pickle
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier

# Load dataset
data = pd.read_csv("patients.csv")

# Convert RiskLevel text to numbers
data["RiskLevel"] = data["RiskLevel"].map({
    "Low": 0,
    "Medium": 1,
    "High": 2
})

# Select features
X = data[["Age", "Weight", "HeartRate"]]

# Target variable
y = data["RiskLevel"]

# Split dataset
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# Train model
model = DecisionTreeClassifier()
model.fit(X_train, y_train)

# Save model
pickle.dump(model, open("risk_model.pkl", "wb"))

print("Model trained successfully!")