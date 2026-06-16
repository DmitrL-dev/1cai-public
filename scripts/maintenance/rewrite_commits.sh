#!/bin/bash
# Скрипт для исправления commit messages через git filter-branch

# Маппинг хешей коммитов на правильные сообщения
declare -A FIXES=(
    ["1d328ff3d9bb6202cd0e8fb4529c949fc12b97a0"]="ci: sync coverage threshold with .coveragerc in perfect-ci-cd"
    ["fd0f5bbb4dc6e470f1e51124cb174c66fc59bea2"]="tests: stabilize environment and stubs for unit/integration"
    ["82f3db07dd1f7b6d70f47a2283b926fa21c2fbf2"]="tests: prepare environment and fix basic errors"
    ["b94d4d4727f367191b72ea42efc27942bfced034"]="policy & observability: add quick entry navigation"
    ["2632117c9995edb2fe8dfcb12edd5ce03cdd0e7f"]="src: document key modules and layers"
    ["3537ec80dc7185d8dda8f1c71b8bba7992236997"]="infrastructure: add navigation and README for components"
    ["48cc2c4503b3e9acb907cccc03ebc8f572d1fd2d"]="scripts: add navigation and README for subdirectories"
    ["9cc94d102b00d12ccc1ed19f38f810338b05a478"]="README: make render_uml.py link clickable"
    ["3a2f5328c1ca47c0cee0b7c76bc6619cc7dbe14f"]="README: make key links clickable"
    ["c077cfb176bfd26aaf7650857303fd90c527d890"]="docs: rework onboarding and navigation"
    ["ddcdad1484a686be26d134b7177e4badb819f0a4"]="docs: add diagram previews in UML catalogs"
    ["2ff1dca9f22fec2f94a785068e9c1e0770205885"]="docs: add navigation for UML diagrams"
    ["b491791645aa2b23d1a948e02e4c292902b2450b"]="README: add explicit diagram generation step"
    ["58036855390e7d15695bbd130f95bfb67ed2b049"]="README: make links in quick overview clickable"
    ["e86fc8c615c5e1e9c87e476b506aa4c66207e6a3"]="README: add quick 30-second overview"
    ["31ba4cd020de978bc659bee82374b04969bb88fe"]="README: restore content block and clarify quickstart"
    ["22660da62be54e07518e343998395e4b3db93b51"]="README: balance introduction and motivation"
    ["312b8db730a983f6c31876c8af6ef98ba5af654a"]="README: add vivid description of motivation"
    ["397144afea59836978d3011c54e7a4609cef8585"]="README: add some self-irony to introduction"
    ["174c300249930ac70331b2172e0ddb9af4053d9d"]="README: improve quickstart and motivation"
    ["1291975b21162d6b59bd78ba6d3e7684972d65b5"]="README: add quickstart and motivation improvements"
    ["30b7340a9c12717dcaddb2901b524feba5ff0b6c"]="README: improve quickstart and motivation"
    ["e1731cd5c37b1a3df5395849bf9c932d6df7f545"]="README: clarify benefits and warmup for quickstart"
    ["c693571498a1831d4cdbabbb2a978ee93012b662"]="docs: improve README: add quick overview and motivation"
    ["3f06288f1660b0728a7e68ec6ac59cdc8f511c42"]="docs: improve README: add quick overview"
)

# Создаем скрипт для filter-branch
cat > /tmp/msg-filter.sh << 'EOF'
#!/bin/bash
COMMIT_HASH="$GIT_COMMIT"
EOF

# Добавляем проверки для каждого коммита
for hash in "${!FIXES[@]}"; do
    echo "if [ \"\$COMMIT_HASH\" = \"$hash\" ]; then" >> /tmp/msg-filter.sh
    echo "  echo \"${FIXES[$hash]}\"" >> /tmp/msg-filter.sh
    echo "  exit" >> /tmp/msg-filter.sh
    echo "fi" >> /tmp/msg-filter.sh
done

echo "cat" >> /tmp/msg-filter.sh
chmod +x /tmp/msg-filter.sh

echo "Running git filter-branch to fix commit messages..."
git filter-branch --msg-filter /tmp/msg-filter.sh -- --all

rm /tmp/msg-filter.sh

echo "Done! Review with: git log --oneline -20"
echo "If satisfied, force push: git push --force-with-lease origin main"

