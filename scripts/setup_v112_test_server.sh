#!/bin/bash

# SpacetimeDB v1.1.2 Test Server Setup Script
# This script helps set up a test server for validation

echo "========================================"
echo "SpacetimeDB v1.1.2 Test Server Setup"
echo "========================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if spacetime CLI is installed
if ! command -v spacetime &> /dev/null; then
    echo -e "${RED}Error: SpacetimeDB CLI not found!${NC}"
    echo "Please install SpacetimeDB first:"
    echo "  curl -sSf https://install.spacetimedb.com | sh"
    exit 1
fi

# Check version
VERSION=$(spacetime version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
echo -e "Found SpacetimeDB version: ${GREEN}$VERSION${NC}"

# Warning for version mismatch
if [[ ! "$VERSION" =~ ^1\.1\.2 ]]; then
    echo -e "${YELLOW}Warning: This script is designed for v1.1.2${NC}"
    echo "Your version is $VERSION"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Configuration
DB_NAME="${SPACETIMEDB_DB:-test-validation}"
HOST="${SPACETIMEDB_HOST:-localhost:3000}"

echo ""
echo "Configuration:"
echo "  Database: $DB_NAME"
echo "  Host: $HOST"
echo ""

# Check if server is running
echo "Checking if SpacetimeDB server is running..."
if curl -s "http://$HOST" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Server is running${NC}"
else
    echo -e "${YELLOW}Server not detected. Starting server...${NC}"
    spacetime server start &
    sleep 5
    
    if curl -s "http://$HOST" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Server started successfully${NC}"
    else
        echo -e "${RED}Failed to start server${NC}"
        exit 1
    fi
fi

# Create test database
echo ""
echo "Creating test database: $DB_NAME"
OUTPUT=$(spacetime database create "$DB_NAME" 2>&1)

if [[ $? -eq 0 ]]; then
    echo -e "${GREEN}✓ Database created successfully${NC}"
    
    # Extract database identity
    DB_IDENTITY=$(echo "$OUTPUT" | grep -oE '[a-f0-9]{64}' | head -1)
    
    if [[ -n "$DB_IDENTITY" ]]; then
        echo -e "${GREEN}Database Identity: $DB_IDENTITY${NC}"
        
        # Save to file for easy access
        echo "$DB_IDENTITY" > .spacetimedb_identity
        
        # Create environment file
        cat > .env.test << EOF
# SpacetimeDB v1.1.2 Test Configuration
export SPACETIMEDB_HOST="$HOST"
export SPACETIMEDB_DB="$DB_NAME"
export SPACETIMEDB_IDENTITY="$DB_IDENTITY"
export SKIP_REAL_SERVER_TESTS="false"
EOF
        
        echo ""
        echo -e "${GREEN}Environment file created: .env.test${NC}"
        echo "To use these settings:"
        echo "  source .env.test"
        
    else
        echo -e "${YELLOW}Warning: Could not extract database identity${NC}"
        echo "You may need to provide it manually"
    fi
else
    if echo "$OUTPUT" | grep -q "already exists"; then
        echo -e "${YELLOW}Database already exists${NC}"
        
        # Try to get existing identity
        if [[ -f .spacetimedb_identity ]]; then
            DB_IDENTITY=$(cat .spacetimedb_identity)
            echo "Using saved identity: $DB_IDENTITY"
        else
            echo "Please provide the database identity manually"
        fi
    else
        echo -e "${RED}Failed to create database${NC}"
        echo "$OUTPUT"
        exit 1
    fi
fi

# Deploy quickstart module if available
if [[ -d "examples/quickstart/server" ]]; then
    echo ""
    echo "Deploying quickstart chat module..."
    
    cd examples/quickstart/server
    OUTPUT=$(spacetime deploy "$DB_NAME" 2>&1)
    
    if [[ $? -eq 0 ]]; then
        echo -e "${GREEN}✓ Module deployed successfully${NC}"
    else
        echo -e "${YELLOW}Warning: Failed to deploy module${NC}"
        echo "You can deploy it manually later"
    fi
    cd ../../..
fi

echo ""
echo "========================================"
echo -e "${GREEN}Setup Complete!${NC}"
echo "========================================"
echo ""
echo "Next steps:"
echo "1. Source the environment file:"
echo "   source .env.test"
echo ""
echo "2. Run the validation tests:"
echo "   python tests/test_v112_real_server.py"
echo ""
echo "3. Run performance benchmarks:"
echo "   python tests/test_v112_performance.py"
echo ""
echo "4. Try the updated quickstart example:"
echo "   python examples/quickstart/client/main_v112.py"
echo ""

if [[ -n "$DB_IDENTITY" ]]; then
    echo "Database Identity: $DB_IDENTITY"
    echo "(Saved to .spacetimedb_identity)"
fi
