import asyncio
import aiohttp
import sys

# Constants extracted from your script
HTTP_HEADERS = {'User-Agent': 'buildroot.org pkg-stats'}

async def get_package_infos(pkg_name):
    async with aiohttp.ClientSession(headers=HTTP_HEADERS) as session:
        # 1. Attempt by Distro (Buildroot)
        url_distro = f"https://release-monitoring.org/api/project/Buildroot/{pkg_name}"
        try:
            async with session.get(url_distro, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    version = data.get('stable_versions', [None])[0] or data.get('version')
                    return {"version": version, "id": data.get('id'), "method": "distro"}
        except Exception:
            pass

        # 2. Attempt by Guess (Pattern) if the first fails
        url_guess = f"https://release-monitoring.org/api/projects/?pattern={pkg_name}"
        try:
            async with session.get(url_guess, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # Filter to find the exact name match
                    projects = [p for p in data.get('projects', []) if p['name'] == pkg_name and p.get('stable_versions')]
                    if projects:
                        # Take the first matched project (sorted by ID as in your original script)
                        projects.sort(key=lambda x: x['id'])
                        return {
                            "version": projects[0]['stable_versions'][0],
                            "id": projects[0]['id'],
                            "method": "guess"
                        }
        except Exception:
            pass

    return None

# Example usage
async def main():
    if len(sys.argv) > 1:
        package = sys.argv[1]
    
        result = await get_package_infos(package)
        
        if result:
            print(f"Paquet: {package}")
            print(f"Dernière version: {result['version']}")
            print(f"ID Projet: {result['id']}")
            print(f"Trouvé via: {result['method']}")
        else:
            print("Version non trouvée.")

if __name__ == "__main__":
    asyncio.run(main())
