**1. Compare three candidate problems: high-activity risk, anomalous activity, and activity drop.**

* **High-Activity Risk:** Predicts whether network volume in a grid exceeds an extreme operational threshold (e.g., top 5th percentile) in the future window. It directly supports proactive capacity planning and traffic monitoring, though it relies on historical volume distributions.
* **Anomalous Activity:** Predicts whether future traffic deviates sharply from regular diurnal baselines (e.g., $Z\text{-score} > 2.5$). It is valuable for detecting localized events or unexpected surges, but carries a higher false-positive rate during scheduled public events.
* **Activity Drop:** Predicts an abrupt collapse in activity toward zero. While relevant for outage identification, physical hardware failures and fiber cuts are sudden, discrete events that are rarely predictable from smooth historical telecommunication features.

---

**2. Select one primary problem for the model.**

* **Selected Problem:** **High-Activity Risk Prediction**.
* **Rationale:** Predicting high-volume activity surges in the upcoming hour provides clear operational value for NOC staff to stage routing policies and monitor critical cells before traffic peaks.

---

**3. Define the prediction unit.**

* **Prediction Unit:** A single spatial grid cell over a discrete hourly observation interval:

$$\text{Unit} = (\text{grid\_id}, t)$$



where $\text{grid\_id} \in [1, 10000]$ and $t$ is the current hourly timestamp cutoff.

---

**4. Define the target as a future window ($t / t+1$ boundary).**

* **Observation Window (Features):** Trailing window strictly ending at timestamp $t$ ($[\text{start\_time}, t]$).
* **Target Window (Label):** The immediate subsequent 1-hour interval $(t, t+1]$.
* **Target Definition:**

$$y_{t+1} = \begin{cases} 1 & \text{if } \text{total\_activity}_{t+1} \ge \text{Threshold} \\ 0 & \text{otherwise} \end{cases}$$


* **Temporal Separation:** All feature engineering inputs must use data strictly prior to or equal to $t$. The label is evaluated exclusively on data generated during $(t, t+1]$.

---

**5. Define the target strategy and document proxy labels.**

* **Strategy:** Synthetic percentile-based proxy labeling.
* **Proxy Definition:** The positive class ($y = 1$) is defined as an hourly activity volume falling within the historical top 5% threshold ($\ge 95\text{th percentile}$) of grid activity.
* **Limitation & Governance Note:** This label serves as an operational proxy for activity density. It reflects statistical volume, not confirmed cell degradation or network failure.

---

**6. Define the business action.**

* **Operational Directive:** *"Flag grid for prioritized NOC human investigation: high probability of an activity surge in interval $t+1$. Review local telemetry, verify scheduled regional events, and monitor uplink margins."*
* **Forbidden Statement:** The system is explicitly forbidden from stating *"The network is congested"* or *"The cell has failed."*

---

**7. Identify data leakage risks and explain how the $t / t+1$ boundary prevents them.**

* **Leakage Risk 1 (Target Leakage):** Including aggregate metrics calculated over the entire dataset (e.g., overall dataset mean or max) leaks future values into historical training instances.
* *Mitigation:* Summary statistics and rolling metrics must be calculated strictly inside the trailing window up to time $t$.


* **Leakage Risk 2 (Circularity / Label Reconstruction):** Computing the label over the same interval as the input features transforms the problem into a simple restatement of a rule, resulting in a trivial near-100% accuracy score.
* *Mitigation:* The $t / t+1$ boundary enforces that features describe momentum up to $t$, while the label evaluates whether that momentum results in a threshold breach at $t+1$.


* **Leakage Risk 3 (Global Scaling Leakage):** Normalizing or scaling features across train and test splits simultaneously allows test distributions to influence training representations.
* *Mitigation:* Scalers and baseline parameters must be fit strictly on training splits prior to application on future time slices.