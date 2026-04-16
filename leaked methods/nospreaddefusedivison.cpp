
void defusedivisonns() {
    while (true) {
        std::this_thread::sleep_for(std::chrono::milliseconds(100));

        if (!globals::rage::exploits || !globals::rage::spreadremove)
            continue;

        try {
            auto replicatedStorageAddr = globals::game::data_model.find_first_child("ReplicatedStorage");
            if (replicatedStorageAddr == 0)
                continue;

            rbx::instance_t replicatedStorage(replicatedStorageAddr);

            auto importAddr = replicatedStorage.find_first_child("Import");
            if (importAddr == 0)
                continue;

            rbx::instance_t importFolder(importAddr);

            auto gunsAddr = importFolder.find_first_child("Guns");
            if (gunsAddr == 0)
                continue;

            rbx::instance_t gunsFolder(gunsAddr);

            auto weaponsAddr = gunsFolder.find_first_child("Weapons");
            if (weaponsAddr == 0)
                continue;

            rbx::instance_t weaponsFolder(weaponsAddr);

            auto weaponChildren = weaponsFolder.get_children();
            if (weaponChildren.empty())
                continue;

            for (auto& weapon : weaponChildren) {
                if (weapon.address == 0)
                    continue;

                auto spreadFolderAddr = weapon.find_first_child("Spread");
                if (spreadFolderAddr == 0)
                    continue;

                rbx::instance_t spreadFolder(spreadFolderAddr);
                auto spreadStates = spreadFolder.get_children();
                if (spreadStates.empty())
                    continue;

                for (auto& state : spreadStates) {
                    if (state.address == 0)
                        continue;

                    std::string className = state.get_class_name();
                    if (className == "NumberValue" || className == "FloatValue") {
                        state.write_float_value(globals::rage::spreadamount);
                    }
                }
            }
        }
        catch (...) {
            continue;
        }
    }
}
```