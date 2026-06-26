import requests
from bs4 import BeautifulSoup
import pathlib

def extract_buildroot_manual(url="https://buildroot.org/downloads/manual/manual.html"):
    """
    Download and keeps only the interesting sections of the Buildroot manual.
    """
        
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Priority sections to extract
    target_sections = [
        # --- Formatting and Submission ---
        "_the_formatting_of_a_patch",                  # Rules about commit message and Signed-off-by
        "_patch_revision_changelog",                   # Management of version history (v2, v3)
        "patch-policy",                                # General patch policy
        "_within_buildroot",                           # Naming convention for .patch files
        "_format_and_licensing_of_the_package_patches", # Patch headers and licenses
        "additional-patch-documentation",              # Upstream tags and CVE
        
        # --- Code Style ---
        "writing-rules-config-in",                     # Kconfig indentation and formatting
        "writing-rules-mk",                            # Format of the .mk file (headers, assignments)
        "package-name-variable-relation",              # Consistency of directory/Kconfig/variable names
        
        # --- Package Metadata and Logic ---
        "generic-package-reference",                   # Complete list of valid variables
        "adding-packages-hash",                        # Format and allowed hash types
        "depends-on-vs-select",                        # When to use 'select' or 'depends on'
        "dependencies-target-toolchain-options",       # Format of dependency comments
        "_start_script_configuration",                 # Structure of SNNfoo startup scripts
        
        # --- Specific Infrastructures ---
        "autotools-package-reference",                 # Autotools specifics
        "cmake-package-reference",                     # CMake specifics
        "python-package-reference",                    # Python specifics
        "virtual-package-tutorial",                    # Rules for virtual packages
        
        # --- Tree Structure ---
        "_package_directory",                          # Allowed location and subdirectories
        "customize-dir-structure"                      # Recommended project file structure
    ]
    
    extracted_rules = []
    
    for section_id in target_sections:
        section = soup.find(id=section_id)
        if section:
            # Retrieve the title and all text until the next section
            title = section.get_text()
            content = []
            for sibling in section.find_next_siblings():
                if sibling.name and sibling.name.startswith('h'): # Stop at the next heading
                    break
                content.append(sibling.get_text(strip=True))
            
            extracted_rules.append({
                "category": "Official Manual",
                "package": "Global",
                "technical_issue": f"Reference: {title}",
                "corrective_action": " ".join(content),
                "status": "manual_rule",
                "patch_id": f"manual_{section_id}"
            })
            
    return extracted_rules


parent_dir = pathlib.Path(__file__).parent.resolve()

doc_path = parent_dir.parent / 'ressources' / 'The_Buildroot_user_manual.html'

rules = extract_buildroot_manual()
with open(doc_path, 'w+', encoding='utf-8') as f:
    f.write('rules = ' + repr(rules) + '\n')
    f.close()

