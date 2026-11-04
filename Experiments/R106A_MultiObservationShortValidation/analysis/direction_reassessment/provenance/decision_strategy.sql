-- Decision synthesis over the reviewed model, acquisition and deployment evidence.
WITH strategies(strategy, application_fit, evidence, recommendation) AS (
  VALUES
    ('Multi-observation as universal mainline', 'Low', 'R106A synthetic and real gates failed', 'Stop'),
    ('Single-image core with optional same-position N=2', 'High', 'Preserves arbitrary-image use; N=2 offers noise/stability support', 'Primary'),
    ('High-resolution multi-frame branch after capture proof', 'Conditional', 'Current two-position phase separation is only 0.161 px median', 'Park as optional R&D')
)
SELECT * FROM strategies;
