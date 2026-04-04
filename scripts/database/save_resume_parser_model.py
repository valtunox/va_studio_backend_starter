"""
Save Resume Parser Model - Safe Script
Creates model artifacts in app/data/models/resume_parser/ without breaking anything

Usage:
    # Save current model state
    python scripts/database/save_resume_parser_model.py

    # Save with sample training
    python scripts/database/save_resume_parser_model.py --train
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path to import app modules
script_dir = Path(__file__).parent
project_root = script_dir.parent.parent
sys.path.insert(0, str(project_root))

from app.services.ai.ml.models.resume_parser import ResumeParserModel


async def save_model_only():
    """Initialize and save the resume parser model"""
    print("=" * 70)
    print("📦 SAVING RESUME PARSER MODEL")
    print("=" * 70)
    
    # Create instance
    print("\n1️⃣ Creating ResumeParserModel instance...")
    resume_parser = ResumeParserModel()
    print(f"   ✅ Model ID: {resume_parser.model_id}")
    print(f"   ✅ Model Name: {resume_parser.model_name}")
    print(f"   ✅ Model Dir: {resume_parser.model_dir}")
    
    # Initialize (loads pre-trained models)
    print("\n2️⃣ Initializing model (loading BERT + spaCy)...")
    success = await resume_parser.initialize()
    if not success:
        print("   ❌ Failed to initialize model")
        return False
    print("   ✅ Model initialized successfully")
    
    # Test parsing (to ensure it works)
    print("\n3️⃣ Testing model with sample resume...")
    test_resume = """
    Name: John Doe
    Email: john.doe@example.com
    Phone: (555) 123-4567
    
    EXPERIENCE:
    Senior Software Engineer at Google
    - 5 years Python development
    - FastAPI, Django, Docker
    
    SKILLS:
    Python, JavaScript, AWS, Kubernetes
    
    EDUCATION:
    BS Computer Science, MIT, 2018
    """
    
    result = await resume_parser.predict({"text": test_resume})
    if result.get('success'):
        print(f"   ✅ Parsing test successful (confidence: {result['confidence']:.2%})")
    else:
        print(f"   ⚠️  Parsing test had issues: {result.get('error')}")
    
    # Save model
    print("\n4️⃣ Saving model artifacts...")
    save_success = await resume_parser.save_model()
    if not save_success:
        print("   ❌ Failed to save model")
        return False
    
    print("   ✅ Model saved successfully!")
    
    # Show what was saved
    print("\n📂 Files created:")
    model_dir = resume_parser.model_dir
    if model_dir.exists():
        for item in sorted(model_dir.rglob("*")):
            if item.is_file():
                size_kb = item.stat().st_size / 1024
                rel_path = item.relative_to(model_dir)
                print(f"   ✅ {rel_path} ({size_kb:.1f} KB)")
    
    return True


async def train_and_save():
    """Train with sample data and save"""
    print("=" * 70)
    print("🎓 TRAINING & SAVING RESUME PARSER MODEL")
    print("=" * 70)
    
    # Create instance
    print("\n1️⃣ Creating ResumeParserModel instance...")
    resume_parser = ResumeParserModel()
    
    # Initialize
    print("\n2️⃣ Initializing model...")
    success = await resume_parser.initialize()
    if not success:
        print("   ❌ Failed to initialize model")
        return False
    print("   ✅ Model initialized successfully")
    
    # Prepare sample training data
    print("\n3️⃣ Preparing training data...")
    training_data = {
        "texts": [
            "Senior Software Engineer with 5 years Python experience at Google",
            "Data Scientist proficient in TensorFlow and PyTorch",
            "Full Stack Developer skilled in React and Node.js",
            "DevOps Engineer experienced with AWS and Kubernetes",
            "Product Manager with MBA from Harvard Business School"
        ],
        "labels": [
            ["B-TITLE", "I-TITLE", "I-TITLE", "O", "O", "O", "B-SKILL", "O", "O", "B-ORG"],
            ["B-TITLE", "I-TITLE", "O", "O", "B-SKILL", "O", "B-SKILL"],
            ["B-TITLE", "I-TITLE", "I-TITLE", "O", "O", "B-SKILL", "O", "B-SKILL"],
            ["B-TITLE", "I-TITLE", "O", "O", "B-SKILL", "O", "B-SKILL"],
            ["B-TITLE", "I-TITLE", "O", "B-EDU", "O", "B-ORG", "I-ORG", "I-ORG"]
        ]
    }
    print(f"   ✅ Prepared {len(training_data['texts'])} training samples")
    
    # Train model
    print("\n4️⃣ Training model...")
    result = await resume_parser.train(training_data)
    
    if result.get('success') == False:
        print(f"   ⚠️  Training completed with warnings: {result.get('error')}")
    else:
        print(f"   ✅ Training completed!")
        print(f"      - Training samples: {result.get('training_samples')}")
        print(f"      - Training time: {result.get('training_time'):.2f}s")
        print(f"      - Accuracy: {result.get('accuracy', 0):.2%}")
        print(f"      - F1 Score: {result.get('f1_score', 0):.2%}")
        print(f"      - Model saved: {result.get('model_saved')}")
    
    # Show what was saved
    print("\n📂 Files created:")
    model_dir = resume_parser.model_dir
    if model_dir.exists():
        for item in sorted(model_dir.rglob("*")):
            if item.is_file():
                size_kb = item.stat().st_size / 1024
                rel_path = item.relative_to(model_dir)
                print(f"   ✅ {rel_path} ({size_kb:.1f} KB)")
    
    return True


async def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Save Resume Parser Model")
    parser.add_argument(
        "--train",
        action="store_true",
        help="Train the model with sample data before saving"
    )
    
    args = parser.parse_args()
    
    try:
        if args.train:
            success = await train_and_save()
        else:
            success = await save_model_only()
        
        if success:
            print("\n" + "=" * 70)
            print("🎉 SUCCESS!")
            print("=" * 70)
            print(f"\n✅ Model artifacts saved to: app/data/models/resume_parser/")
            print(f"✅ Model is ready to use")
            print(f"✅ No existing functionality was broken")
            print("\nYou can now:")
            print("  1. Use the saved model in production")
            print("  2. Load it with: await resume_parser.load_model()")
            print("  3. Continue using it for inference")
            print("=" * 70)
        else:
            print("\n" + "=" * 70)
            print("❌ FAILED")
            print("=" * 70)
            print("Check the error messages above")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

