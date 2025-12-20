import fitz  # PyMuPDF
import os

def create_sample_pdf(output_path):
    doc = fitz.open()
    page = doc.new_page()
    
    text = """
    Document Intelligence Service - Test Document
    
    This is a sample document for testing the extraction capabilities of the Document Intelligence Service.
    
    1. Project Kick-off Meeting
    Date: 2026-04-01
    Time: 10:00 AM
    Participants: Project Team, Stakeholders
    
    2. Budget Approval
    The budget of $50,000 for the first phase must be approved by 2026-03-25.
    
    3. Documentation Submission
    All technical documentation should be submitted as a PDF by 2026-05-15.
    
    4. Hardware Procurement
    Purchase 5 new workstations by the end of April (2026-04-30). Total estimated cost: $12,500.
    
    5. Weekly Status Report
    Every Friday at 4:00 PM.
    
    Contact: support@docintel.com
    """
    
    # Simple text insertion
    page.insert_text((50, 50), text)
    
    doc.save(output_path)
    doc.close()
    print(f"Sample PDF created at: {output_path}")

if __name__ == "__main__":
    create_sample_pdf("sample_test.pdf")
