import pandas as pd
from sklearn.tree import DecisionTreeClassifier
import pickle

# Sample training data
data = {
    "age": [25, 45, 65, 30, 55, 70, 40, 50],
    "heart_rate": [72, 90, 110, 80, 95, 120, 85, 100],
    "risk": ["Low", "Medium", "High", "Low", "Medium", "High", "Medium", "High"]
}

df = pd.DataFrame(data)

X = df[["age", "heart_rate"]]
y = df["risk"]

model = DecisionTreeClassifier()
model.fit(X, y)

# Save trained model
pickle.dump(model, open("risk_model.pkl", "wb"))

print("✅ Model trained and saved as risk_model.pkl")