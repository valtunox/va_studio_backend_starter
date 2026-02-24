# Training CLI - Quick Reference Guide

## Installation

The CLI is ready to use! No additional installation needed.

## Usage

### Windows:
```bash
# Using batch file (from project root)
scripts\train.bat train resume_parser

# Or directly with Python
python scripts/train_cli.py train resume_parser
```

### Linux/Mac:
```bash
# Using shell script (from project root)
./scripts/train.sh train resume_parser

# Or directly with Python
python scripts/train_cli.py train resume_parser
```

## Commands

### 1. Train Models

Train a specific model:
```bash
# Train resume parser
python scripts/train_cli.py train resume_parser --data app/data/resume.csv

# Train job matching
python scripts/train_cli.py train job_matching --data app/data/linkdin_Job_data.csv

# Train salary prediction
python scripts/train_cli.py train salary_prediction

# Train with incremental data
python scripts/train_cli.py train resume_parser --data new_data.csv --incremental
```

Train all models:
```bash
python scripts/train_cli.py train all
```

### 2. List Datasets

View all available training datasets:
```bash
python scripts/train_cli.py datasets list
```

### 3. Validate Data

Validate training data before training:
```bash
python scripts/train_cli.py validate --data app/data/resume.csv --model resume_parser
```

### 4. Upload Training Data

Upload new data and optionally auto-train:
```bash
# Upload only
python scripts/train_cli.py upload --data new_resumes.csv --model resume_parser

# Upload and auto-train
python scripts/train_cli.py upload --data new_resumes.csv --model resume_parser --auto-train
```

### 5. Check Training Status

See current training progress:
```bash
python scripts/train_cli.py status
```

### 6. View Training History

View past training runs:
```bash
python scripts/train_cli.py history
```

## Examples

### Complete Training Workflow:

```bash
# 1. List available datasets
python scripts/train_cli.py datasets list

# 2. Validate your data
python scripts/train_cli.py validate --data app/data/resume.csv --model resume_parser

# 3. Train the model
python scripts/train_cli.py train resume_parser --data app/data/resume.csv

# 4. Check status
python scripts/train_cli.py status

# 5. View history
python scripts/train_cli.py history
```

### Incremental Training:

```bash
# Add new data and train incrementally
python scripts/train_cli.py upload --data new_data.csv --model resume_parser --auto-train

# Or train incrementally with existing data
python scripts/train_cli.py train resume_parser --data new_data.csv --incremental
```

## Supported Models

- `resume_parser` - Resume parsing and NER
- `job_matching` - Job-to-candidate matching
- `salary_prediction` - Salary prediction model
- `candidate_ranking` - Candidate ranking model
- `interview_scoring` - Interview scoring model
- `all` - Train all models

## Data Formats

### Resume Parser:
```json
{
  "texts": ["resume text 1", "resume text 2"],
  "categories": ["IT", "ENGINEERING"]
}
```

### Job Matching:
```json
{
  "job_descriptions": ["job description 1", "job description 2"],
  "position_titles": ["Software Engineer", "Data Scientist"],
  "companies": ["Company A", "Company B"]
}
```

## Troubleshooting

### Import Errors:
Make sure you're running from the project root directory:
```bash
cd ai_agents
python scripts/train_cli.py train resume_parser
```

### Virtual Environment:
If using a virtual environment, activate it first:
```bash
# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

## Help

Get help for any command:
```bash
python scripts/train_cli.py --help
python scripts/train_cli.py train --help
```

