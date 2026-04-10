# Git-Based Component Registry Research

**Date:** 2026-04-10  
**Epic:** [#77 - Pivot to Agent-Centric Registry](https://github.com/BlazeUp-AI/Observal/issues/77)  
**Related:** [#79 - Git Mirroring Service](https://github.com/BlazeUp-AI/Observal/issues/79)

## Executive Summary

Research into how production package registries (Docker Hub, Homebrew, Cargo, Go modules, Pip) handle git-based component mirroring and discovery. The simplest pattern that works: **shallow clone + manifest file + convention fallback**.

## Registries Analyzed

### 1. Docker Hub Automated Builds
- **Discovery**: Explicit configuration (NOT auto-scan)
- **Pattern**: Users specify Dockerfile path relative to build context
- **Mono-repos**: Supported via build context path configuration
- **Philosophy**: Clarity and control over automatic scanning

### 2. Homebrew Taps
- **Discovery**: Convention-based (`homebrew-something` repo naming)
- **Pattern**: Formulas as Ruby files in `Formula/` directory
- **Mono-repos**: One tap = multiple formulas
- **Updates**: API-based (formulae.brew.sh JSON) with local repo fallback
- **Versioning**: Explicit version + revision field for patches

### 3. Cargo (Rust Package Manager)
- **Clone**: Full clone (NOT shallow)
- **Caching**: Complete repo in local cache
- **Versioning**: `branch`, `tag`, `rev` keys in Cargo.toml
- **Mono-repos**: Auto-traverses entire tree to find all `Cargo.toml` files
- **Locking**: `Cargo.lock` pins exact git commit SHAs
- **Submodules**: Fetched recursively by default

### 4. Go Modules
- **Clone**: Extracts specific revision (efficient, minimal transfer)
- **Caching**: `$GOPATH/pkg/mod` (read-only by default)
- **Versioning**: Semantic version tags (`v1.2.3`)
- **Pseudo-versions**: For untagged commits (`v0.0.0-timestamp-hash`)
- **Mono-repos**: Multiple modules via subdirectories in path
- **Discovery**: Module path = repo root + subdirectory + version suffix

### 5. Pip (Python Package Installer)
- **Clone**: Partial clone with `--filter=blob:none` (Git 2.17+)
- **Caching**: Immutability-based (checks if revision is mutable)
- **Versioning**: Resolves branches/tags/commits to SHA1
- **Environment**: Unsets `GIT_DIR`, `GIT_WORK_TREE` to avoid interference

### 6. MCP Servers Monorepo
- **Structure**: `/src/{server-name}/` directories
- **Discovery**: `.mcp.json` manifest file at root
- **Pattern**: Reference implementations as examples

## Clone Strategy Comparison

| Strategy | Used By | Pros | Cons | Best For |
|----------|---------|------|------|----------|
| **Full clone** | Cargo | Complete history, checkout any commit | Slow, high bandwidth/disk | Development workflows |
| **Shallow (`--depth 1`)** | Git docs | Fast, minimal disk | Can't switch branches easily | Registries, CI/CD |
| **Partial (`--filter=blob:none`)** | Pip | Fast, fetch blobs on-demand | Requires Git 2.17+ | Large repos |
| **Revision extract** | Go | Efficient for specific version | Complex implementation | Mature systems |

**Recommendation for Observal**: Shallow clone (`--depth 1 --single-branch`)

## Discovery Mechanisms Comparison

| Approach | Used By | Implementation |
|----------|---------|----------------|
| **Manifest file** | MCP, npm, Go | `.mcp.json`, `package.json`, `go.mod` at root |
| **Convention** | Homebrew | `Formula/{letter}/{name}.rb` structure |
| **Tree traversal** | Cargo | Recursive search for `Cargo.toml` files |
| **Explicit config** | Docker Hub | User specifies all paths |

**Recommendation for Observal**: Manifest file (primary) + convention scan (fallback)

## Recommendations for Observal

### The Simplest Pattern That Works

```bash
# 1. Initial sync
git clone --depth 1 --single-branch --branch main \
  https://github.com/org/repo.git \
  /var/lib/observal/mirrors/{sha256(git_url)}

# 2. Re-sync (periodic)
cd /var/lib/observal/mirrors/{sha256(git_url)} && \
  git fetch origin && \
  git reset --hard origin/main

# 3. Discovery
# Primary: Look for .observal.json or observal.json
# Fallback: Scan /src/*, /packages/*, /components/*

# 4. Validation per component type
# MCPs: grep -r "from mcp.server.fastmcp import FastMCP"
# Skills: Check for SKILL.md
# Hooks: Validate hook.json schema
```

### Manifest File Format

**Option A: Manifest-based (recommended)**

```json
// .observal.json or observal.json at repo root
{
  "version": "1.0",
  "mcps": [
    {
      "path": "src/filesystem",
      "name": "filesystem-mcp",
      "description": "File system operations MCP server"
    },
    {
      "path": "src/git",
      "name": "git-mcp",
      "description": "Git operations MCP server"
    }
  ],
  "skills": [
    {
      "path": "skills/tdd",
      "name": "tdd-skill",
      "description": "Test-driven development skill"
    }
  ],
  "hooks": [
    {
      "path": "hooks/pre-commit",
      "name": "security-check-hook"
    }
  ]
}
```

**Option B: Convention-based (fallback when no manifest)**

- MCPs: `/src/*`, `/mcps/*`, `/servers/*` (directories containing `__main__.py` or `server.py`)
- Skills: `/skills/*` (directories containing `SKILL.md`)
- Hooks: `/hooks/*` (directories containing `hook.json`)
- Prompts: `/prompts/*` (`.md` or `.txt` files)
- Sandboxes: `/sandboxes/*` (directories containing `Dockerfile`)

### Clone Strategy Details

1. **Shallow clone for initial sync** (fast, minimal disk):
   ```bash
   git clone --depth 1 --single-branch --branch main <url> <dir>
   ```

2. **Cache locally** in content-addressed directory:
   ```
   /var/lib/observal/mirrors/
     ├── abc123def456.../ (sha256 of github.com/org/repo1)
     └── 789ghi012jkl.../ (sha256 of gitlab.com/org/repo2)
   ```

3. **Re-sync** via fetch + reset (don't re-clone):
   ```bash
   cd /var/lib/observal/mirrors/{hash} && \
   git fetch origin && \
   git reset --hard origin/main
   ```

4. **Cleanup**: LRU eviction when disk usage > 80%

### Mono-Repo Support

1. **Manifest explicitly declares components** (recommended)
2. **OR auto-discover via convention scan**
3. **Each component gets separate database entry**:
   - `git_url`: Same for all components in mono-repo
   - `component_path`: Subdirectory (e.g., `src/filesystem`)
   - `git_ref`: Commit SHA at sync time

**Example**: MCP servers repo at `github.com/modelcontextprotocol/servers`
- Single git_url for all servers
- Each server has unique component_path (`src/filesystem`, `src/git`, etc.)
- All share same git_ref (commit SHA)

### Versioning Strategy

**Simple approach** (MVP):
- Store commit SHA in `git_ref` field
- Users specify branch/tag when adding source
- Resolve to SHA during sync

**Future enhancements**:
- Support semver tags (`v1.2.3`)
- Version constraints in agent manifests (`^1.0.0`)
- Pseudo-versions like Go (`v0.0.0-20230101120000-abc123def456`)

### Caching & Cleanup

| Aspect | Strategy | Rationale |
|--------|----------|-----------|
| **Caching** | Keep mirrors indefinitely | Cheap disk, expensive network |
| **Cleanup** | LRU when disk > 80% | Simple, predictable |
| **Re-sync** | Periodic (hourly/daily) | Check `auto_sync_interval` field |
| **Invalidation** | None (just re-sync) | Simple, effective |

### What NOT to Overcomplicate

1. **No semver resolution** (yet): Just store commit SHA, no version constraint solving
2. **No submodules**: Clone with defaults, ignore submodule edge cases
3. **No Git LFS**: Regular git only, no large file support
4. **HTTPS only**: SSH keys optional, don't build key management MVP
5. **Two discovery methods max**: Manifest OR convention, no more
6. **No incremental scanning**: Full re-scan on sync (fast enough for typical repos)
7. **Simple retry logic**: 3 attempts with exponential backoff, then fail

### Error Handling

1. **Network failures**: Retry 3x with backoff (1s, 2s, 4s), mark `sync_status: failed`
2. **Invalid repos**: Log detailed error, set `sync_error` field, continue processing
3. **Missing manifest**: Fall back to convention scan (not an error)
4. **No components found**: Warn but allow (components might be added later)
5. **FastMCP validation fails**: Reject MCP with detailed error message
6. **Malformed manifest**: JSON validation error, reject source

## Implementation Pseudo-Code

```python
def sync_component_source(source_id: str) -> SyncResult:
    """
    Sync a git repository and discover/validate components.
    
    Steps:
    1. Clone or update local mirror
    2. Discover components (manifest OR convention)
    3. Validate each component
    4. Upsert to database
    5. Update sync status
    """
    source = db.query(ComponentSource).get(source_id)
    mirror_dir = get_mirror_path(source.git_url)
    
    try:
        # Step 1: Clone or pull
        if not mirror_dir.exists():
            run_command(f"""
                git clone --depth 1 --single-branch 
                --branch {source.branch or 'main'}
                {source.git_url} {mirror_dir}
            """)
        else:
            run_command(f"""
                cd {mirror_dir} && 
                git fetch origin && 
                git reset --hard origin/{source.branch or 'main'}
            """)
        
        # Step 2: Discover components
        components = discover_components(mirror_dir, source.component_type)
        
        # Step 3: Validate
        for comp in components:
            validate_component(comp, mirror_dir)
        
        # Step 4: Upsert to database
        commit_sha = get_commit_sha(mirror_dir)
        for comp in components:
            upsert_component_listing(
                component_type=source.component_type,
                name=comp.name,
                git_url=source.git_url,
                component_path=comp.path,
                git_ref=commit_sha,
                is_private=source.is_public == False,
                owner_org_id=source.owner_org_id
            )
        
        # Step 5: Update sync status
        source.last_synced_at = datetime.utcnow()
        source.sync_status = 'success'
        source.sync_error = None
        db.session.commit()
        
        return SyncResult(success=True, components_found=len(components))
        
    except Exception as e:
        source.sync_status = 'failed'
        source.sync_error = str(e)
        db.session.commit()
        return SyncResult(success=False, error=str(e))


def discover_components(mirror_dir: Path, component_type: str) -> List[Component]:
    """
    Discover components using manifest OR convention.
    """
    # Try manifest first
    manifest_path = mirror_dir / '.observal.json'
    if not manifest_path.exists():
        manifest_path = mirror_dir / 'observal.json'
    
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        return parse_manifest_components(manifest, component_type)
    
    # Fallback to convention scan
    return scan_by_convention(mirror_dir, component_type)


def scan_by_convention(mirror_dir: Path, component_type: str) -> List[Component]:
    """
    Scan directory tree for components using conventions.
    """
    search_dirs = {
        'mcp': ['src', 'mcps', 'servers'],
        'skill': ['skills'],
        'hook': ['hooks'],
        'prompt': ['prompts'],
        'sandbox': ['sandboxes']
    }
    
    components = []
    for base_dir in search_dirs.get(component_type, []):
        search_path = mirror_dir / base_dir
        if search_path.exists():
            for item in search_path.iterdir():
                if is_valid_component(item, component_type):
                    components.append(Component(
                        name=item.name,
                        path=str(item.relative_to(mirror_dir))
                    ))
    
    return components


def validate_component(comp: Component, mirror_dir: Path):
    """
    Validate component based on type.
    Raises ValidationError if invalid.
    """
    comp_path = mirror_dir / comp.path
    
    if comp.type == 'mcp':
        # Check for FastMCP usage
        if not any((comp_path / '**' / '*.py').glob('*')):
            raise ValidationError("No Python files found")
        
        python_files = list(comp_path.rglob('*.py'))
        fastmcp_found = any(
            'from mcp.server.fastmcp import FastMCP' in f.read_text()
            or 'from fastmcp import FastMCP' in f.read_text()
            for f in python_files
        )
        
        if not fastmcp_found:
            raise ValidationError(
                "MCP must use FastMCP. "
                "See: https://modelcontextprotocol.io/fastmcp"
            )
    
    elif comp.type == 'skill':
        skill_md = comp_path / 'SKILL.md'
        if not skill_md.exists():
            raise ValidationError("Skills must have SKILL.md file")
    
    elif comp.type == 'hook':
        hook_json = comp_path / 'hook.json'
        if not hook_json.exists():
            raise ValidationError("Hooks must have hook.json file")
        
        # Validate JSON schema
        hook_config = json.loads(hook_json.read_text())
        validate_hook_schema(hook_config)
    
    # Add more validation as needed


def get_mirror_path(git_url: str) -> Path:
    """
    Get consistent mirror directory for a git URL.
    Uses SHA256 hash to avoid path issues.
    """
    url_hash = hashlib.sha256(git_url.encode()).hexdigest()
    return Path('/var/lib/observal/mirrors') / url_hash
```

## Database Schema Integration

Works with schema from [agent-centric-schema-design.md](../superpowers/specs/2026-04-10-agent-centric-schema-design.md):

```sql
-- component_sources table tracks git repos
CREATE TABLE component_sources (
    id UUID PRIMARY KEY,
    url TEXT NOT NULL,
    provider VARCHAR(50) NOT NULL,  -- 'github', 'gitlab', 'bitbucket'
    component_type VARCHAR(50) NOT NULL,  -- 'mcp', 'skill', 'hook', 'prompt', 'sandbox'
    is_public BOOLEAN NOT NULL DEFAULT true,
    owner_org_id UUID REFERENCES organizations(id),
    auto_sync_interval INTERVAL,  -- e.g., '1 day', '6 hours'
    last_synced_at TIMESTAMPTZ,
    sync_status VARCHAR(20),  -- 'pending', 'syncing', 'success', 'failed'
    sync_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Each component listing links to source via git_url + component_path
-- (fields in mcp_listings, skill_listings, etc.)
ALTER TABLE mcp_listings ADD COLUMN component_path VARCHAR(500) DEFAULT '/';
ALTER TABLE skill_listings ADD COLUMN component_path VARCHAR(500) DEFAULT '/';
-- etc.
```

## Background Jobs

### Sync Worker

```python
# Runs every minute, checks auto_sync_interval
def component_sync_worker():
    while True:
        sources = db.query(ComponentSource).filter(
            ComponentSource.auto_sync_interval.isnot(None),
            or_(
                ComponentSource.last_synced_at.is_(None),
                ComponentSource.last_synced_at + ComponentSource.auto_sync_interval < datetime.utcnow()
            )
        ).all()
        
        for source in sources:
            sync_component_source(source.id)
        
        time.sleep(60)  # Check every minute
```

### Cleanup Worker

```python
# Runs daily, removes least-used mirrors when disk > 80%
def mirror_cleanup_worker():
    while True:
        disk_usage = get_disk_usage('/var/lib/observal/mirrors')
        
        if disk_usage > 0.80:  # 80% full
            # Get mirror access times
            mirrors = sorted(
                Path('/var/lib/observal/mirrors').iterdir(),
                key=lambda p: p.stat().st_atime  # Access time
            )
            
            # Remove oldest until disk < 70%
            for mirror in mirrors:
                if get_disk_usage('/var/lib/observal/mirrors') < 0.70:
                    break
                shutil.rmtree(mirror)
                logger.info(f"Removed mirror: {mirror.name}")
        
        time.sleep(86400)  # Daily
```

## API Endpoints

```python
# Add new component source
POST /api/v1/component-sources
{
  "url": "https://github.com/org/repo.git",
  "component_type": "mcp",
  "is_public": true,
  "auto_sync_interval": "1 day"
}

# List sources
GET /api/v1/component-sources?component_type=mcp

# Trigger manual sync
POST /api/v1/component-sources/{id}/sync

# Get sync status
GET /api/v1/component-sources/{id}/status
```

## Implementation Checklist

- [ ] `component_sources` table with sync fields
- [ ] Git clone wrapper with retry logic
- [ ] Manifest parser (JSON schema validation)
- [ ] Convention scanner (directory traversal)
- [ ] FastMCP validator (grep for import statement)
- [ ] Skill validator (check for SKILL.md)
- [ ] Hook validator (JSON schema validation)
- [ ] Component upsert logic (create/update listings)
- [ ] Background sync worker
- [ ] Background cleanup worker
- [ ] API endpoints (CRUD for sources, manual sync)
- [ ] Error handling and logging
- [ ] Tests (unit + integration)

## Timeline Estimate

- **Day 1**: `component_sources` table, basic git clone wrapper
- **Day 2**: Manifest parser + convention scanner
- **Day 3**: FastMCP/skill/hook validation logic
- **Day 4**: Database upsert, background sync worker
- **Day 5**: Error handling, cleanup worker, API endpoints, testing

**Total: ~1 week for MVP git mirroring service**

## Success Criteria

- [ ] Can clone public GitHub/GitLab repos
- [ ] Discovers components via manifest OR convention
- [ ] Validates FastMCP usage for MCPs
- [ ] Creates/updates component listings in database
- [ ] Handles mono-repos (multiple components per repo)
- [ ] Re-syncs on schedule (auto_sync_interval)
- [ ] Gracefully handles errors (network failures, invalid repos)
- [ ] Cleans up old mirrors when disk full

## Future Enhancements (Post-MVP)

1. **Semver version constraints**: Support `^1.0.0`, `~2.1.0` in agent manifests
2. **SSH key support**: Private repos via SSH
3. **Webhook triggers**: GitHub/GitLab webhooks for instant sync
4. **Incremental sync**: Only re-scan changed files (git diff)
5. **Submodule support**: Handle repos with submodules
6. **Git LFS support**: Large file storage
7. **Component dependency graph**: Track MCP dependencies
8. **Multi-branch support**: Track multiple branches per source
9. **Tag-based versioning**: Explicit version pinning via git tags
10. **Rollback support**: Revert to previous sync state

## References

- [Agent-Centric Schema Design](../superpowers/specs/2026-04-10-agent-centric-schema-design.md)
- [Product Vision](../superpowers/specs/2026-04-10-product-vision.md)
- [Git Clone Documentation](https://git-scm.com/docs/git-clone)
- [Cargo Book - Dependencies](https://doc.rust-lang.org/cargo/reference/specifying-dependencies.html)
- [Go Modules Reference](https://go.dev/ref/mod)
- [Homebrew Taps](https://docs.brew.sh/Taps)
- [MCP Servers Repository](https://github.com/modelcontextprotocol/servers)
