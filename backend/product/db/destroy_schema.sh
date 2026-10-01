#!/usr/bin/env bash
# use this script like this.
# ./destroy.sh monday monday_staging public

MYDIR="$(dirname "${0}")"

SCHEMAS=("$@")

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
        echo "- ERROR: No schemas provided. Pass schema names as arguments."
        echo "  Example: ./destroy.sh Patients Nurses CarePlan"
        _RC=1
    fi

    if [[ ${_RC} != 0 ]]; then
        echo "ERROR: Some pre-requisites are not met, terminating!"
        exit ${_RC}
    fi
}

function run_destroy() {
    __DEFAULT_PG_URI=postgresql://postgres:changeme@localhost/atlas

    if [[ -z "${PG_URI}" ]]; then
        echo -n "Enter the Connection URI to the target database (or use default \"${__DEFAULT_PG_URI}\"): "
        read PG_URI
        if [[ -z "${PG_URI}" ]]; then
            PG_URI="${__DEFAULT_PG_URI}"
            echo "Using default: ${PG_URI}"
        fi
    else
        echo "The value for \${PG_URI} is read from a variable."
    fi

    _LOG="${MYDIR}/destroy.log"
    truncate -s 0 "${_LOG}"

    echo "Dropping schemas: ${SCHEMAS[*]}"

    DROP_SQL=""
    for s in "${SCHEMAS[@]}"; do
        DROP_SQL+="DROP SCHEMA IF EXISTS \"${s}\" CASCADE;"
    done

    echo -e "${DROP_SQL}"

    psql "${PG_URI}" <<EOF | tee "${_LOG}"
${DROP_SQL}
EOF
}

sanity_check
run_destroy
