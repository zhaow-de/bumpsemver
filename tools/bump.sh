#!/usr/bin/env bash


function extract_version_content() {
  changelog=$1
  target_version=$2

  awk -v target="$target_version" '
    /^## / {
      if (found) exit;
      version=$2;
      if (version == target) found=1;
      next;
    }
    found { print; }
  ' <<< "$changelog"
}

#rm -Rf dist
#RELEASE_KIND=$(generate-changelog --output release-hint)
#echo "::notice::Suggested release type is: ${RELEASE_KIND}"
#PR_NUMBER=$(gh pr view --json number -q .number || echo "")
#echo "::notice::PR number is: ${PR_NUMBER}"
#export PR_NUMBER
#bumpsemver bump -v $RELEASE_KIND
#python -m build
#python -m twine upload dist/*

changelog=$(cat "CHANGELOG.md")
TARGET_VERSION=$(bumpsemver show current_version)
echo "TAG_NAME=$TARGET_VERSION"
NOTES=$(extract_version_content "$changelog" "$TARGET_VERSION")


gh release create \
  "${TARGET_VERSION}" \
  ./dist/* \
  --title "${TARGET_VERSION}" \
  --notes "${NOTES}" \
  --draft \
