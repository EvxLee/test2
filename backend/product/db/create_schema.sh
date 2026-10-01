#!/usr/bin/env bash
# use this script like this.
# ./create_schema.sh monday monday_staging

MYDIR="$(dirname "${0}")"

SCHEMAS=("$@")   # array of schema names passed as args

function sanity_check() {
    _RC=0
    _BINARIES=("psql")

    echo "Checking all tools are accessible..."
    for b in ${_BINARIES[*]}; do
        if ! which "${b}" >/dev/null 2>&1; then
            echo -e "\t- ERROR: You probably don't have \"${b}\" installed."
            _RC=1
        fi
    done

    if [[ ${#SCHEMAS[@]} -eq 0 ]]; then
        echo "- ERROR: No schema names provided."
        echo "  Usage: ./create_schemas.sh Schema1 Schema2 Schema3"
        _RC=1
    fi

    if [[ ${_RC} != 0 ]]; then
        echo "ERROR: Some pre-requisites are not met, terminating!"
        exit ${_RC}
    fi
}

function run_create() {
    __DEFAULT_PG_URI=postgresql://postgres:changeme@localhost/atlas

    if [[ -z "${PG_URI}" ]]; then
        echo -n "Enter the Connection URI to the target database (or use default \"${__DEFAULT_PG_URI}\"): "
        read PG_URI
        if [[ -z "${PG_URI}" ]]; then
            PG_URI="${__DEFAULT_PG_URI}"
            echo "Using default: ${PG_URI}"
        fi
    else
        echo "The value for \${PG_URI} is read from the environment."
    fi

    _LOG="${MYDIR}/create_schemas.log"
    truncate -s 0 "${_LOG}"

    SQL=""
    for s in "${SCHEMAS[@]}"; do
        SQL+="CREATE SCHEMA IF NOT EXISTS \"${s}\";"
    done

    echo "Creating schemas: ${SCHEMAS[*]}"
    echo -e "${SQL}" | tee -a "${_LOG}"

    psql "${PG_URI}" <<EOF | tee -a "${_LOG}"
${SQL}
EOF
}

sanity_check
run_create
