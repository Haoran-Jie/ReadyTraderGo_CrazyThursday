cmake -DCMAKE_BUILD_TYPE=Debug -B build
cmake --build build --config Debug
cp build/autotrader .
echo ---- Ready to run! -----
python3 rtg.py run autotrader