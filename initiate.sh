sudo rm -rf build
echo ----remove the cache, done!----
cmake -DCMAKE_BUILD_TYPE=Release -B build
cmake --build build --config Release
cp build/autotrader .
echo ---- Ready to run! -----
python3 rtg.py run autotrader