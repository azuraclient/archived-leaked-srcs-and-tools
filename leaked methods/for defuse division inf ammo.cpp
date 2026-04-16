void ddinfammo() {
    while (true) {
        std::this_thread::sleep_for(std::chrono::milliseconds(100));

        if (!globals::rage::exploits || !globals::rage::infammo)
            continue;

        try {
            if (globals::game::data_model.address == 0)
                continue;

            auto ugcAddr = globals::game::data_model.find_first_child("Ugc");
            if (ugcAddr == 0)
                continue;

            rbx::instance_t ugc(ugcAddr);

            auto replicatedStorageAddr = ugc.find_first_child("ReplicatedStorage");
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

                auto ammoAddr = weapon.find_first_child("Ammo");
                if (ammoAddr == 0)
                    continue;

                rbx::instance_t ammo(ammoAddr);
                if (ammo.address == 0)
                    continue;

                ammo.write_int_value(globals::rage::ammo_value);
            }
        }
        catch (...) {
            continue;
        }
    }
}