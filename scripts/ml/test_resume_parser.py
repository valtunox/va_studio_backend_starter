#!/usr/bin/env python3
"""
Test the trained Resume Parser model directly (without API server)
Run: python scripts/test_resume_parser.py
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

async def test_resume_parser():
    print("=" * 60)
    print("Testing Trained Resume Parser Model")
    print("=" * 60)
    
    # Import the model
    from app.services.ai.ml.models import ResumeParserModel, RESUME_PARSER_AVAILABLE
    
    if not RESUME_PARSER_AVAILABLE:
        print("[ERROR] ResumeParserModel not available!")
        return
    
    # Initialize the model
    print("\n[1] Initializing Resume Parser Model...")
    model = ResumeParserModel()
    success = await model.initialize()
    print(f"    Initialized: {success}")
    print(f"    Model loaded from: models/resume_parser/")
    
    # Test resume samples
    test_resumes = [
        {
            "name": "Python Developer Resume",
            "text": """
Name: John Smith
Title: Senior Python Developer

Professional Summary:
Experienced Python Developer with 8 years of expertise in Django, FastAPI, and AWS.
Strong background in building scalable web applications and microservices.

Work Experience:
- Senior Python Developer at Tech Solutions Inc. (New York, NY) 2020-Present
  Led team of 5 developers, implemented CI/CD pipelines, reduced deployment time by 60%
- Python Engineer at Data Systems Corp. (Boston, MA) 2017-2020
  Built RESTful APIs serving 1M+ requests daily
- Junior Developer at StartupXYZ (Austin, TX) 2015-2017
  Full-stack development with Python/Django

Education:
- Master of Science in Computer Science at MIT, 2015
- Bachelor of Science in Software Engineering at Stanford, 2013

Skills: Python, Django, FastAPI, Flask, AWS, Docker, Kubernetes, PostgreSQL, Redis, 
        Machine Learning, TensorFlow, Git, CI/CD, Agile, Scrum

Certifications:
- AWS Certified Solutions Architect
- Google Cloud Professional

Contact: john.smith@email.com | (555) 123-4567 | linkedin.com/in/johnsmith
"""
        },
        {
            "name": "Database Administrator Resume",
            "text": """
Name: Sarah Johnson
Title: Senior Oracle Database Administrator

Summary:
10+ years of experience in Oracle and PostgreSQL database administration.
Expert in performance tuning, backup/recovery, and high availability solutions.

Experience:
- Senior DBA at Fortune 500 Company, Chicago, IL (2018-Present)
  Managed 50+ production databases, implemented RAC clustering
- Oracle DBA at Tech Corp, Denver, CO (2014-2018)
  Database migration projects, 99.99% uptime achievement

Education:
- BS in Information Technology, Georgia Tech, 2014

Technical Skills:
Oracle 12c/19c, PostgreSQL, MySQL, PL/SQL, T-SQL, AWS RDS, Azure SQL,
Database Tuning, Backup & Recovery, RMAN, Data Guard, RAC

Email: sarah.j@email.com | Phone: 555-987-6543
"""
        },
        {
            "name": "Web Developer Resume",
            "text": """
Jane Doe
Frontend Developer | React Specialist

About Me:
Creative frontend developer with 5 years of experience building modern web applications.
Passionate about UI/UX and creating responsive, accessible interfaces.

Work History:
* Lead Frontend Developer - Digital Agency NYC (2021-Present)
  React, TypeScript, Next.js, 20+ client projects
* Web Developer - E-commerce Company (2019-2021)
  Built product pages, checkout flows, A/B testing
* Junior Developer - Startup (2018-2019)
  HTML, CSS, JavaScript, jQuery

Education:
Web Development Bootcamp, General Assembly, 2018
BA in Graphic Design, Parsons School of Design, 2017

Skills: React, Vue.js, Angular, TypeScript, JavaScript, HTML5, CSS3, 
Tailwind CSS, Node.js, REST APIs, GraphQL, Figma, Git

Portfolio: janedoe.dev | Email: jane@email.com
"""
        }
    ]
    
    # Test each resume
    for i, sample in enumerate(test_resumes, 1):
        print(f"\n{'='*60}")
        print(f"[{i}] Testing: {sample['name']}")
        print("=" * 60)
        
        try:
            result = await model.predict(sample['text'])
            
            if result.get('success'):
                parsed = result.get('parsed_data', {})
                
                print(f"\n[OK] Parsing successful!")
                print(f"    Confidence: {result.get('confidence', 0):.2%}")
                print(f"    Processing time: {result.get('processing_time', 0):.3f}s")
                print(f"    Entities found: {result.get('entities_found', 0)}")
                
                # Personal Info
                personal = parsed.get('personal_info', {})
                if personal:
                    print(f"\n    Personal Info:")
                    if personal.get('name'):
                        print(f"      Name: {personal.get('name')}")
                    if personal.get('title'):
                        print(f"      Title: {personal.get('title')}")
                
                # Contact Info
                contact = parsed.get('contact_info', {})
                if contact:
                    print(f"\n    Contact Info:")
                    if contact.get('email'):
                        print(f"      Email: {contact.get('email')}")
                    if contact.get('phone'):
                        print(f"      Phone: {contact.get('phone')}")
                    if contact.get('linkedin'):
                        print(f"      LinkedIn: {contact.get('linkedin')}")
                
                # Skills
                skills = parsed.get('skills', {})
                if skills:
                    print(f"\n    Skills Extracted:")
                    for skill_type, skill_list in skills.items():
                        if skill_list:
                            print(f"      {skill_type}: {', '.join(skill_list[:5])}{'...' if len(skill_list) > 5 else ''}")
                
                # Experience
                experience = parsed.get('experience', {})
                if experience:
                    print(f"\n    Experience:")
                    if experience.get('total_years'):
                        print(f"      Total Years: {experience.get('total_years')}")
                    positions = experience.get('positions', [])
                    if positions:
                        print(f"      Positions: {len(positions)} found")
                        for pos in positions[:2]:
                            print(f"        - {pos}")
                
                # Education
                education = parsed.get('education', [])
                if education:
                    print(f"\n    Education:")
                    for edu in education[:2]:
                        print(f"      - {edu}")
                
            else:
                print(f"[ERROR] Parsing failed: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            print(f"[ERROR] Exception: {e}")
    
    print("\n" + "=" * 60)
    print("Resume Parser Test Complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_resume_parser())

