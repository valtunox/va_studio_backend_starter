"""
valtunox AI HR & cloudsystem Platform - Training CLI
Command-line interface for training AI models
"""

import argparse
import json
import sys
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional
import pandas as pd

# Add parent directory to path (scripts folder -> project root)
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.training.data_loader import DataLoader
from app.training.model_trainer import ModelTrainer
from app.training.training_utils import TrainingDataValidator, DataPreprocessor


def print_success(message: str):
    """Print success message"""
    print(f"✅ {message}")


def print_error(message: str):
    """Print error message"""
    print(f"❌ {message}", file=sys.stderr)


def print_info(message: str):
    """Print info message"""
    print(f"ℹ️  {message}")


async def train_model_async(model_name: str, data_source: Optional[str] = None, 
                           incremental: bool = False):
    """Train a model asynchronously"""
    try:
        trainer = ModelTrainer()
        loader = DataLoader()
        
        # Load data
        if data_source:
            print_info(f"Loading data from {data_source}...")
            if model_name == "resume_parser":
                data = loader.load_for_resume_parser(data_source)
            elif model_name == "job_matching":
                data = loader.load_for_job_matching(data_source)
            elif model_name == "salary_prediction":
                data = loader.load_for_salary_prediction(data_source)
            elif model_name == "candidate_ranking":
                data = loader.load_for_candidate_ranking(data_source)
            elif model_name == "interview_scoring":
                data = loader.load_for_interview_scoring(data_source)
            else:
                print_error(f"Unknown model: {model_name}")
                return
        else:
            data = None
        
        # Train model
        print_info(f"Training {model_name}...")
        if incremental and data:
            result = await trainer.train_model_with_data(model_name, data)
        elif model_name == "resume_parser":
            result = await trainer.train_resume_parser(data if data else None)
        elif model_name == "job_matching":
            result = await trainer.train_job_matching(data if data else None)
        elif model_name == "salary_prediction":
            result = await trainer.train_salary_prediction(data if data else None)
        elif model_name == "candidate_ranking":
            result = await trainer.train_candidate_ranking(data if data else None)
        elif model_name == "interview_scoring":
            result = await trainer.train_interview_scoring(data if data else None)
        else:
            print_error(f"Unknown model: {model_name}")
            return
        
        print_success(f"{model_name} training completed!")
        print(f"Metrics: {json.dumps(result, indent=2, default=str)}")
        
    except Exception as e:
        print_error(f"Training failed: {e}")
        sys.exit(1)


def train_model(model_name: str, data_source: Optional[str] = None, 
               incremental: bool = False):
    """Train a model"""
    asyncio.run(train_model_async(model_name, data_source, incremental))


def train_all_models():
    """Train all models"""
    try:
        trainer = ModelTrainer()
        print_info("Training all models...")
        result = asyncio.run(trainer.train_all_models())
        print_success("All models trained successfully!")
        print(f"Results: {json.dumps(result, indent=2, default=str)}")
    except Exception as e:
        print_error(f"Training failed: {e}")
        sys.exit(1)


def list_datasets():
    """List all available datasets"""
    try:
        loader = DataLoader()
        summary = loader.get_dataset_summary()
        
        print("\n📊 Available Datasets:")
        print("=" * 60)
        
        datasets = summary.get("datasets", {})
        if not datasets:
            print("No datasets found")
            return
        
        for name, info in datasets.items():
            print(f"\n📁 {name}")
            if "error" in info:
                print(f"   ⚠️  Error: {info['error']}")
            else:
                print(f"   📏 Size: {info.get('file_size_mb', 0)} MB")
                print(f"   📋 Columns: {', '.join(info.get('columns', []))}")
                if info.get('row_count'):
                    print(f"   📊 Rows: {info['row_count']}")
                print(f"   🕒 Modified: {info.get('last_modified', 'N/A')}")
        
        print("\n" + "=" * 60)
        
    except Exception as e:
        print_error(f"Failed to list datasets: {e}")
        sys.exit(1)


def validate_data(data_file: str, model_type: str):
    """Validate training data"""
    try:
        loader = DataLoader()
        validator = TrainingDataValidator()
        
        print_info(f"Loading data from {data_file}...")
        
        # Load data based on model type
        if model_type == "resume_parser":
            data = loader.load_for_resume_parser(data_file)
        elif model_type == "job_matching":
            data = loader.load_for_job_matching(data_file)
        elif model_type == "salary_prediction":
            data = loader.load_for_salary_prediction(data_file)
        else:
            print_error(f"Unknown model type: {model_type}")
            return
        
        print_info(f"Validating data for {model_type}...")
        result = validator.validate(data, model_type)
        
        print("\n📋 Validation Results:")
        print("=" * 60)
        print(f"✅ Valid: {result.get('valid', False)}")
        
        if result.get('errors'):
            print("\n❌ Errors:")
            for error in result['errors']:
                print(f"   - {error}")
        
        if result.get('warnings'):
            print("\n⚠️  Warnings:")
            for warning in result['warnings']:
                print(f"   - {warning}")
        
        if result.get('statistics'):
            print("\n📊 Statistics:")
            for key, value in result['statistics'].items():
                print(f"   {key}: {value}")
        
        print("=" * 60)
        
        if not result.get('valid'):
            sys.exit(1)
        
    except Exception as e:
        print_error(f"Validation failed: {e}")
        sys.exit(1)


def show_training_status():
    """Show training status"""
    try:
        trainer = ModelTrainer()
        status = trainer.get_training_status()
        
        print("\n🔧 Training Status:")
        print("=" * 60)
        
        if status.get('is_training'):
            print(f"🔄 Currently training: {status.get('current_model')}")
            print(f"📊 Progress: {status.get('progress', 0)}%")
            print(f"🕒 Started: {status.get('start_time', 'N/A')}")
        else:
            print("✅ No training in progress")
        
        if status.get('error'):
            print(f"❌ Error: {status['error']}")
        
        if status.get('training_history_count', 0) > 0:
            print(f"\n📜 Training History: {status['training_history_count']} entries")
            last_training = status.get('last_training')
            if last_training:
                print(f"   Last: {last_training.get('model')} at {last_training.get('timestamp')}")
        
        print("=" * 60)
        
    except Exception as e:
        print_error(f"Failed to get training status: {e}")
        sys.exit(1)


def show_training_history():
    """Show training history"""
    try:
        trainer = ModelTrainer()
        history = trainer.training_history
        
        print("\n📜 Training History:")
        print("=" * 60)
        
        if not history:
            print("No training history found")
            return
        
        for i, entry in enumerate(history[-10:], 1):  # Show last 10
            print(f"\n{i}. {entry.get('model', 'Unknown')} - {entry.get('timestamp', 'N/A')}")
            if entry.get('incremental'):
                print("   📈 Incremental training")
            if entry.get('data_samples'):
                print(f"   📊 Samples: {entry['data_samples']}")
            if entry.get('metrics'):
                metrics = entry['metrics']
                if isinstance(metrics, dict):
                    if 'accuracy' in metrics:
                        print(f"   ✅ Accuracy: {metrics.get('accuracy', 0):.2%}")
                    if 'f1_score' in metrics:
                        print(f"   📈 F1 Score: {metrics.get('f1_score', 0):.2%}")
        
        print("\n" + "=" * 60)
        
    except Exception as e:
        print_error(f"Failed to get training history: {e}")
        sys.exit(1)


def upload_data(data_file: str, model_type: str, auto_train: bool = False):
    """Upload training data"""
    try:
        loader = DataLoader()
        validator = TrainingDataValidator()
        preprocessor = DataPreprocessor()
        
        print_info(f"Loading data from {data_file}...")
        
        # Load data based on model type
        if model_type == "resume_parser":
            data = loader.load_for_resume_parser(data_file)
        elif model_type == "job_matching":
            data = loader.load_for_job_matching(data_file)
        elif model_type == "salary_prediction":
            data = loader.load_for_salary_prediction(data_file)
        else:
            print_error(f"Unknown model type: {model_type}")
            return
        
        # Validate
        print_info("Validating data...")
        validation_result = validator.validate(data, model_type)
        
        if not validation_result.get('valid'):
            print_error(f"Validation failed: {validation_result.get('errors')}")
            sys.exit(1)
        
        # Preprocess
        print_info("Preprocessing data...")
        if model_type == "resume_parser":
            processed_data = preprocessor.preprocess_for_resume_parser(data)
        elif model_type == "job_matching":
            processed_data = preprocessor.preprocess_for_job_matching(data)
        else:
            processed_data = data
        
        # Remove duplicates
        processed_data = preprocessor.remove_duplicates(processed_data)
        
        # Save
        from datetime import datetime
        filename = f"{model_type}_incremental_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        saved_path = loader.save_training_data(processed_data, filename)
        
        print_success(f"Data uploaded and saved to: {saved_path}")
        print(f"   Samples: {len(processed_data.get('texts', processed_data.get('job_descriptions', [])))}")
        
        if auto_train:
            print_info("Starting training...")
            train_model(model_type, data_source=data_file, incremental=True)
        
    except Exception as e:
        print_error(f"Upload failed: {e}")
        sys.exit(1)


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="AI Model Training CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Train resume parser model
  python train_cli.py train resume_parser --data app/data/resume.csv
  
  # Train all models
  python train_cli.py train all
  
  # List available datasets
  python train_cli.py datasets list
  
  # Validate data
  python train_cli.py validate --data app/data/resume.csv --model resume_parser
  
  # Upload and auto-train
  python train_cli.py upload --data app/data/resume.csv --model resume_parser --auto-train
  
  # Check training status
  python train_cli.py status
  
  # Show training history
  python train_cli.py history
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Train command
    train_parser = subparsers.add_parser('train', help='Train a model')
    train_parser.add_argument('model', choices=['resume_parser', 'job_matching', 
                                                 'salary_prediction', 'candidate_ranking', 
                                                 'interview_scoring', 'all'],
                              help='Model to train')
    train_parser.add_argument('--data', '--data-source', dest='data_source',
                             help='Path to training data file')
    train_parser.add_argument('--incremental', action='store_true',
                             help='Use incremental training')
    
    # Datasets command
    datasets_parser = subparsers.add_parser('datasets', help='Manage datasets')
    datasets_parser.add_argument('action', choices=['list'], help='Action to perform')
    
    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Validate training data')
    validate_parser.add_argument('--data', '--file', dest='data_file', required=True,
                                help='Path to data file')
    validate_parser.add_argument('--model', '--model-type', dest='model_type', required=True,
                                choices=['resume_parser', 'job_matching', 'salary_prediction'],
                                help='Model type')
    
    # Upload command
    upload_parser = subparsers.add_parser('upload', help='Upload training data')
    upload_parser.add_argument('--data', '--file', dest='data_file', required=True,
                              help='Path to data file')
    upload_parser.add_argument('--model', '--model-type', dest='model_type', required=True,
                              choices=['resume_parser', 'job_matching', 'salary_prediction'],
                              help='Model type')
    upload_parser.add_argument('--auto-train', action='store_true',
                             help='Automatically train after upload')
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Show training status')
    
    # History command
    history_parser = subparsers.add_parser('history', help='Show training history')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    try:
        if args.command == 'train':
            if args.model == 'all':
                train_all_models()
            else:
                train_model(args.model, args.data_source, args.incremental)
        
        elif args.command == 'datasets':
            if args.action == 'list':
                list_datasets()
        
        elif args.command == 'validate':
            validate_data(args.data_file, args.model_type)
        
        elif args.command == 'upload':
            upload_data(args.data_file, args.model_type, args.auto_train)
        
        elif args.command == 'status':
            show_training_status()
        
        elif args.command == 'history':
            show_training_history()
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

